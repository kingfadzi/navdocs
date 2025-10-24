# Key Concepts

System architecture and design principles for the PPM deployment pipeline.

---

## Design Principles

**Two-BOM System**
- `baseline.yaml` - ALL infrastructure entities (Object Types, Validations, Commands)
- `functional.yaml` - SPECIFIC business logic (Workflows, Request Types, Reports)

**File-Based Triggering**
- Pipeline detects which BOM files changed
- Runs only relevant deployments
- Both changed? Baseline runs first, then functional

**Baseline-First Execution**
- Infrastructure must exist before business logic
- Prevents dependency failures
- Enforced by pipeline ordering

**Manual Rollback**
- Deliberate action, not automatic
- Uses archived bundles
- 3-tier retrieval (GitLab -> S3 -> local)

**Mock-First Testing**
- Local mode uses mock scripts
- No real PPM servers needed
- Same commands for dev and prod

---

## Core Components

### BOMs (Bill of Materials)

**Baseline BOM** - Infrastructure sync
```yaml
version: "1.0"
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
# No entities list - profile defines what's deployed
```

**Functional BOM** - Specific entities
```yaml
version: "1.0"
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
entities:
  - entity_id: workflow
    reference_code: "WF_INCIDENT_MGMT"
    description: "Incident workflow"
```

### Profiles

**What they do:**
- Define which entity types to include
- Control dependency handling (add missing or require baseline)
- Compile to 25-character Y/N flag strings for kMigrator

**Two profiles:**
- `baseline.yaml` - Infrastructure (7 entity types, add_missing=true)
- `functional-cd.yaml` - Business logic (14 entity types, add_missing=false)

**Flag compilation:**
```
baseline.yaml -> YYYYYNNNNYYYYYNNNNNNNNNNN
functional-cd.yaml -> NYYYYYNYYNNNYYYYYYYYYYN
```

### Pipeline

**Main pipeline** (`.gitlab-ci.yml`):
1. **Validate** - Check BOM against governance rules
2. **Generate** - Create child pipeline based on changed files
3. **Deploy** - Trigger child pipeline

**Child pipeline** (per BOM):
1. **Extract** - Pull entities from source server
2. **Import** - Push entities to target server
3. **Archive** - Create rollback package

### Tool Structure

```
tools/
- deployment/       # Core deployment logic
  - orchestrator.py  # Main entry point
  - archive.py       # Rollback packages
  - utils.py         # Shared utilities
- config/           # Configuration & validation
  - validation.py    # BOM validator
  - flags.py         # Flag compiler
  - pipeline.py      # Pipeline generator
- executors/        # Execution abstraction
  - local.py         # Mock mode
  - remote.py        # SSH + S3
- storage/          # Storage abstraction
  - local.py         # Filesystem
  - s3.py            # S3/MinIO
```

---

## Storage Architecture

**Local Storage** (development)
- Config: `storage_backend: "local"`
- Bundles: `./bundles/` directory
- Archives: `./archives/` directory
- Use case: Testing without PPM servers

**S3/MinIO Storage** (production)
- Config: `storage_backend: "s3"`
- Bundles: S3 bucket + GitLab artifacts
- Archives: S3 (permanent) + GitLab (1 year)
- Use case: Production deployments

**Bundle flow in S3 mode:**
```
Extract: PPM Server -> Runner -> GitLab artifacts
Import: GitLab artifacts -> Runner -> PPM Server
Archive: Create ZIP -> S3 (permanent) + GitLab artifacts
```

---

## Execution Modes

**Local Executor** (mock mode)
- Triggered: No `ssh_host` OR `storage_backend: "local"`
- Scripts: Mock kMigrator in `./mock/`
- Storage: Local filesystem
- Use case: Testing, development

**Remote Executor** (production)
- Triggered: `ssh_host` set AND `storage_backend: "s3"`
- Scripts: Real kMigrator via SSH
- Storage: S3/MinIO
- Use case: Actual deployments

**Auto-selection:**
```python
if ssh_host AND storage_backend == 's3':
    RemoteExecutor (SSH + S3)
else:
    LocalExecutor (mock)
```

**Activation:**
- Local: `export DEPLOYMENT_ENV=local`
- Remote: Don't set DEPLOYMENT_ENV

---

## Vault Integration

**Secrets from HashiCorp Vault**
- GitLab CI components fetch from Vault
- Export as environment variables
- No credentials in code or config

**Per-server vault roles:**
```yaml
servers:
  dev-ppm-useast:
    vault_roles:
      - name: ppm-dev
        path: secret/data/ppm/dev/useast
```

**Exported variables:**
- `PPM_ADMIN_USER` / `PPM_ADMIN_PASSWORD` - PPM credentials
- `SSH_USERNAME` / `SSH_PASSWORD` - SSH credentials
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - S3 credentials

**Pipeline workflow:**
1. Vault component fetches secrets
2. Exports as environment variables
3. Deployment tools read from environment
4. Secrets cleared after job

---

## Entity Categories

### Baseline Entities (Infrastructure)

Must exist before functional deployments.

| Entity | ID | Purpose | Change Freq |
|--------|----|---------| ------------|
| Object Types | 26 | Define object structure | Quarterly |
| Request Header Types | 39 | Define request forms | Quarterly |
| Validations | 13 | Lookup lists and rules | Monthly |
| User Data Contexts | 37 | Shared custom fields | Quarterly |
| Special Commands | 11 | Backend functions | As-needed |
| Environments | 4 | Deployment targets | Rarely |
| Environment Groups | 58 | Target groups | Rarely |

**Philosophy:** Drift correction (add_missing=true)

### Functional Entities (Business Logic)

Deploy frequently once baseline is stable.

| Entity | ID | Purpose | Change Freq |
|--------|----|---------| ------------|
| Workflows | 9 | Process flows | Weekly |
| Request Types | 19 | Request forms | Weekly |
| Report Types | 17 | Reports | Weekly |
| Overview Page Sections | 61 | Overview page layouts | Weekly |
| Dashboard Modules | 470 | Dashboard pages | Weekly |
| Dashboard Data Sources | 505 | SQL queries behind portlets | Weekly |
| Portlet Definitions | 509 | Dashboard widgets | Weekly |
| Project Types | 521 | Project templates | Monthly |
| Work Plan Templates | 522 | Standard task breakdowns | Monthly |
| Program Types | 901 | Program-level structure | Monthly |
| Portfolio Types | 903 | Portfolio hierarchy | Monthly |
| OData Data Sources | 906 | OData-backed queries | Weekly |
| Custom Menu | 907 | Custom UI menu entries | As-needed |
| Chatbot Intent | 908 | Chatbot intents (PPM 25.2+) | Weekly |
| PPM Integration SDK | 9900 | PPM SDK objects | As-needed |

**Philosophy:** Assumes baseline exists (add_missing=false)

---

## Governance Rules

Defined in `config/rules.yaml`, enforced during validation.

**Critical rules (enabled):**

1. **Promotion Order** - Must follow: dev -> test -> staging -> prod (no skipping)
2. **Rollback Required** - All deployments must set `rollback_pipeline_id`
3. **Change Request** - Production/staging require `change_request` field
4. **Source != Target** - Prevents self-deployment
5. **Branch-Environment Alignment** - Branch must match target environment
   - `feature/*` -> test only
   - `develop` -> staging only
   - `main` -> prod only

**Enforcement:**
- Validation runs before deployment
- Blocking failures stop deployment
- Test locally: `python3 -m tools.config.validation --file boms/baseline.yaml --branch main`

---

## Rollback Strategy

**3-Tier Retrieval**

Rollback archives retrieved in priority order:

1. **GitLab Artifacts** (primary) - 1 year retention, fastest
2. **S3 Cold Storage** (fallback) - Permanent retention
3. **Local Filesystem** (dev) - `archives/` directory

**Archive contents:**
- `bundles/` - Entity XML files
- `bom.yaml` - Original BOM
- `flags.txt` - Exact 25-character flags used
- `manifest.yaml` - Deployment metadata

**Rollback process:**
1. Set `rollback_pipeline_id` in BOM
2. Run: `python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml`
3. System retrieves archive (GitLab -> S3 -> local)
4. Validates target server matches
5. Redeploys using original flags

**Key principle:** Uses exact flags from original deployment for consistency.

**Manifest structure:**
```yaml
rollback_bundle_path: archives/CR-12345-archive.zip
s3_snapshot_url: s3://bucket/12345/snapshot.tar.gz
storage_backend: s3
deployment_metadata:
  deployment_type: functional
  target_server: test-ppm-useast
  flags: "NYNNNYYYYNNNYYYYYYYYYYN"
```

---

## Approval & Branching

**Branch strategy:**

| Branch | Deploys To | Approvals |
|--------|------------|-----------|
| `feature/*` | Test | 2 |
| `develop` | Staging | 2 |
| `main` | Prod | 3+ |

**Promotion workflow:**
1. Feature branch -> Edit BOM (target: test) -> MR -> Deploy to test
2. Update target to staging -> MR to develop -> Deploy to staging
3. Update target to prod, add rollback_pipeline_id -> MR to main -> Deploy to prod

**CODEOWNERS:**
- `boms/baseline.yaml` -> `@platform-team` required
- Production BOMs -> `@tech-leads` + `@ops-team` required
- `profiles/*.yaml` -> `@platform-team` required

---

## Configuration Files

**Production:** `config/deployment-config.yaml`
- Real server hostnames
- S3 storage
- Real kMigrator paths
- Vault roles

**Local override:** `config/deployment-config.local.yaml`
- `ssh_host: null` (disable SSH)
- `storage_backend: local` (use filesystem)
- Mock script paths
- Simple credential env vars

**Governance:** `config/rules.yaml`
- Validation rules
- Severity (blocking/warning)
- Environment filters

**BOMs:** `boms/*.yaml`
- Define what to deploy
- Version controlled
- Trigger pipeline on change

**Profiles:** `profiles/*.yaml`
- Define deployment flags
- Entity lists (baseline only)
- Compiled to Y/N strings

---

## Key Workflows

**Baseline Deployment** (infrastructure sync)
- Deploys ALL 7 baseline entity types
- Add missing dependencies (drift correction)
- High risk - affects all downstream entities
- Quarterly or as-needed

**Functional Deployment** (business logic)
- Deploys ONLY entities listed in BOM
- Requires baseline to exist
- Medium risk - isolated to specific entities
- Weekly or sprint-based

**Rollback** (restore previous)
- Manual action, not automatic
- Uses archived bundles
- Same approval requirements as forward deployment
- Fast - no extraction needed

---

## Environment Variables

**Local mode:**
```bash
export DEPLOYMENT_ENV=local
export PPM_ADMIN_USER=testuser
export PPM_ADMIN_PASSWORD=testpass
```

**Remote mode:**
```bash
# Don't set DEPLOYMENT_ENV
# All credentials injected by Vault in pipeline
# For manual CLI: export SSH_USERNAME, SSH_PASSWORD, PPM_ADMIN_USER, etc.
```

See [MANUAL_DEPLOYMENT_GUIDE.md](MANUAL_DEPLOYMENT_GUIDE.md) for complete credential setup.

---

## Benefits

**Platform Engineers:**
- No manual flag strings (auto-compiled from profiles)
- No manual kMigrator commands (automated)
- Instant rollback from artifacts

**Operations:**
- Clear approval gates
- BOM review shows exactly what changes
- Complete audit trail (Git + artifacts)

**Developers:**
- Test locally without PPM servers
- Same tooling for all environments
- Fast automated deployments

---

## References

- [MANUAL_DEPLOYMENT_GUIDE.md](MANUAL_DEPLOYMENT_GUIDE.md) - CLI commands and manual deployments
- [KMIGRATOR_REFERENCE.md](KMIGRATOR_REFERENCE.md) - kMigrator technical reference
- [OpenText PPM Documentation](https://admhelp.microfocus.com/ppm/)
