# Pipeline Architecture

How the GitLab pipeline executes deployments.

---

## Two-Tier Design

**Main Pipeline** - Detects changes, validates, triggers child pipelines
**Child Pipeline** - Executes deployment (extract -> import -> archive)

**Trigger:** Commit to `boms/baseline.yaml` or `boms/functional.yaml`

---

## Main Pipeline Flow

```
File Change
    |
    v
Validate (BOM + governance rules)
    |
    v
Generate (create child-pipeline.yml)
    |
    v
Trigger (start child pipeline)
```

### Stages

| Stage | Job | Runs When | Command | Output |
|-------|-----|-----------|---------|--------|
| validate | validate_baseline | baseline.yaml changed | `validation.py` | Pass/fail |
| validate | validate_functional | functional.yaml changed | `validation.py` | Pass/fail |
| generate | generate_baseline_pipeline | baseline.yaml changed | `pipeline.py` | baseline-child-pipeline.yml |
| generate | generate_functional_pipeline | functional.yaml changed | `pipeline.py` | functional-child-pipeline.yml |
| deploy | trigger_baseline | baseline.yaml changed | Trigger child | Baseline child pipeline |
| deploy | trigger_functional | functional.yaml changed | Trigger child | Functional child pipeline |

### Change Detection

| Files Changed | Result |
|---------------|--------|
| baseline.yaml only | Baseline pipeline runs |
| functional.yaml only | Functional pipeline runs |
| Both files | Baseline runs first, then functional |
| Neither file | No deployment |

**Baseline-first ordering:** `needs: [trigger_baseline_deployment]` with `optional: true`

---

## Child Pipeline Flow

```
Extract Stage
  SSH to source -> kMigratorExtract.sh -> Download to runner -> GitLab artifacts
    |
    v
Import Stage (needs: extract)
  Download artifacts -> SSH to target -> kMigratorImport.sh
    |
    v
Archive Stage (needs: extract, import)
  Create ZIP -> S3 (permanent) + GitLab artifacts (1 year)
```

### Stages

| Stage | Command | Process | Artifacts | Retention |
|-------|---------|---------|-----------|-----------|
| extract | `orchestrator extract` | SSH -> kMigrator -> Download to runner | bundles/*.xml, metadata.yaml | 1 week |
| import | `orchestrator import` | Artifacts -> SSH -> kMigrator | None | N/A |
| archive | `orchestrator archive` | ZIP -> S3 + artifacts | archive.zip, evidence.zip, manifest.yaml | 1 year |

---

## Vault Integration

Credentials injected per stage via GitLab components.

### Extract Stage
- SSH credentials (source server)
- PPM credentials

### Import Stage
- SSH credentials (target server)
- PPM credentials

### Archive Stage
- S3 write credentials

**Flow:** Vault component -> Environment variables -> Orchestrator reads -> Job completes -> Credentials cleared

---

## Artifact Strategy

**Why both S3 and GitLab Artifacts?**

| Storage | Retention | Purpose |
|---------|-----------|---------|
| GitLab Artifacts | 1 week (bundles), 1 year (archives) | Fast access for next stages, recent rollback |
| S3 | Permanent | Long-term rollback (6+ months old) |

**Bundle flow:**
```
Extract: PPM -> Runner -> GitLab artifacts (1 week)
Import: GitLab artifacts -> Runner -> PPM
Archive: Create ZIP -> S3 (permanent) + GitLab artifacts (1 year)
```

---

## Dynamic Pipeline Generation

`tools.config.pipeline` generates child pipelines.

**Input:**
- BOM file (source_server, target_server, profile)
- Server vault roles (from deployment-config.yaml)

**Output:**
- Child pipeline YAML with vault components
- Saved as GitLab artifact
- Triggered by main pipeline

**Why dynamic?**
- Vault components vary per server
- BOM content determines deployment type
- One template, many configurations

---

## Error Handling

| Stage | Failure | Result |
|-------|---------|--------|
| Validate | BOM invalid | Pipeline stops, no deployment |
| Generate | Template error | Pipeline stops, no deployment |
| Extract | SSH/kMigrator fails | Import/archive skipped, pipeline fails |
| Import | SSH/kMigrator fails | Archive still runs (creates rollback), pipeline marked failed |
| Archive | S3/ZIP fails | No rollback package, pipeline fails |

---

## Files Involved

| File | Purpose | Used By |
|------|---------|---------|
| `.gitlab-ci.yml` | Main pipeline definition | GitLab |
| `templates/child-pipeline-template.yml` | Child pipeline template | Pipeline generator |
| `boms/*.yaml` | Trigger changes, define deployments | All stages |
| `config/deployment-config.yaml` | Server/vault configuration | Orchestrator, generator |
| `config/rules.yaml` | Governance rules | Validation |
| `profiles/*.yaml` | Flag compilation | Orchestrator |

---

## Key Design Decisions

**Why two-tier pipeline?**
- Main pipeline is static (simple, predictable)
- Child pipelines are dynamic (adapt to BOM)
- Clear separation of concerns

**Why baseline before functional?**
- Infrastructure dependencies must exist first
- `optional: true` only enforces when both change
- Prevents import failures

**Why generate child pipelines?**
- Vault components vary per server
- BOM determines deployment parameters
- Single template, dynamic configuration

**Why separate validate/generate/trigger?**
- Fast feedback (validation fails early)
- Generated pipeline reviewable in artifacts
- Clear audit trail

---

## Quick Reference

**Main pipeline:** `.gitlab-ci.yml`
- 3 stages: validate -> generate -> deploy
- Triggers: File changes in `boms/`
- Output: Child pipeline YAML

**Child pipeline:** `templates/child-pipeline-template.yml`
- 3 stages: extract -> import -> archive
- Input: BOM file, vault credentials
- Output: Rollback package (1 year retention)

**Vault:** Per-stage credential injection
- Extract/Import: SSH + PPM
- Archive: S3 write

**Artifacts:** Two-tier storage
- GitLab: Fast, limited retention
- S3: Permanent, long-term rollback

**Ordering:** Baseline always before functional
- Only enforced when both files change
- `needs: [baseline]` with `optional: true`
