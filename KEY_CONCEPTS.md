# Key Concepts

System architecture and design principles for the PPM deployment pipeline.

---

## Design Principles

**Two-BOM System**
- `baseline.yaml` - SPECIFIC infrastructure entities listed explicitly (Object Types, Validations, Commands)
- `functional.yaml` - SPECIFIC business logic entities listed explicitly (Workflows, Request Types, Reports)

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

**What BOMs define:**
- WHAT specific entities to deploy
- Category (baseline or functional)
- Source and target servers
- Validated against JSON schemas

**Baseline BOM** - Specific infrastructure entities
```yaml
version: "1.0"
category: baseline
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
entities:
  - id: 26
    reference_code: "OBJ_CUSTOM_ASSET"
    name: "Custom Asset Object Type"
  - id: 13
    reference_code: "VAL_PRIORITY_LEVELS"
    name: "Priority Levels Validation"
```

**Functional BOM** - Specific business logic entities
```yaml
version: "2.0"
category: functional
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
entities:
  - id: 9
    reference_code: "WF_INCIDENT_MGMT"
    name: "Incident Management Workflow"
  - id: 19
    reference_code: "REQ_TYPE_INCIDENT"
    name: "Incident Request Type"
```

### Profiles and Flag Compilation

**Separation of Concerns:**
- **BOM** = WHAT to deploy (entities list)
- **Profile** = HOW to deploy (flags configuration)

**What profiles do:**
- Define flag configuration ONLY (not entities)
- Control replacement behavior (replace vs add_missing)
- Compile to 25-character Y/N flag strings for kMigrator

**What profiles do NOT do:**
- Define which entities to deploy (that's in the BOM)
- Determine entity types to extract (that's in the BOM)

**Two profiles:**
- `baseline.yaml` - Baseline flags (add_missing=true for drift correction)
- `functional-cd.yaml` - Functional flags (add_missing=false for strict dependencies)

**Profile structure:**
```yaml
# profiles/functional-cd.yaml
flags:
  replace_object_type: false       # Flag 1
  replace_request_type: true       # Flag 2
  replace_request_header_type: false  # Flag 3
  replace_special_command: false   # Flag 4
  replace_validation: false        # Flag 5
  replace_workflow: true           # Flag 6
  replace_report_type: true        # Flag 7
  # ... 18 more flags
```

**Flag compiler:**

The flag compiler (`tools/config/flags.py`) converts YAML profiles to 25-character strings:

```bash
# Compile baseline profile
python3 -m tools.config.flags baseline
# Output: YNYYYNNNNYYYNYNNNNNNNNNNNN

# Compile functional-cd profile
python3 -m tools.config.flags functional-cd
# Output: NYNNNYYYYNNNYNYYYYYYYYYYY
```

**Benefits:**
- Human-readable flag configuration
- Version-controlled in Git
- Self-documenting (each flag has descriptive name)
- Prevents typos in 25-character strings

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
  - s3.py            # S3
```

---

## Storage Architecture

**Local Storage** (development)
- Config: `storage_backend: "local"`
- Bundles: `./bundles/` directory
- Archives: `./archives/` directory
- Use case: Testing without PPM servers

**S3 Storage** (production)
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
- Storage: S3
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

## Secret Management

**Central Secrets Manager Integration**
- GitLab CI components fetch secrets automatically
- Export as environment variables
- No credentials in code or config

**Per-server secrets configuration:**
```yaml
servers:
  dev-ppm-useast:
    ssh_env_vars:
      username: "SSH_USERNAME"      # Variable name from secrets manager
      password: "SSH_PASSWORD"
    ppm_api_env_vars:
      username: "PPM_ADMIN_USER"
      password: "PPM_ADMIN_PASSWORD"
    vault_roles:
      - name: ppm-dev
        path: secret/data/ppm/dev/useast
```

**Variable names are configurable:**
- Variable names depend on the secrets manager in use
- Defined in `deployment-config.yaml` per server (`ssh_env_vars`, `ppm_api_env_vars`)
- Deployment tools read variable names from config, not hardcoded
- Example above shows one possible configuration

**Pipeline workflow:**
1. Secrets manager fetches credentials from configured paths
2. Exports as environment variables (names defined in config)
3. Deployment tools read variables specified in config
4. Secrets cleared after job

---

## Entity Categories

### Baseline Entities (Infrastructure)

Must exist before functional deployments.

**Complete list:** See [Entity Reference](ENTITY_REFERENCE.md#baseline-entities-infrastructure---7-entities)

**Baseline entities (7):** Object Types (26), Request Header Types (39), Validations (13), User Data Contexts (37), Special Commands (11), Environments (4), Environment Groups (58)

**Philosophy:** Drift correction enabled (add_missing=true)

### Functional Entities (Business Logic)

Deploy frequently once baseline is stable.

**Complete list:** See [Entity Reference](ENTITY_REFERENCE.md#functional-entities-business-logic---15-entities)

**Functional entities (15):** Workflows (9), Request Types (19), Reports (17), Overview Pages (61), Dashboards (470, 505, 509), Project/Program/Portfolio Types (521, 901, 903), Work Plans (522), OData Sources (906), Custom Menu (907), Chatbot Intents (908), PPM SDK (9900)

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
- Secrets configuration

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
# All credentials injected by Central Secrets Manager in pipeline
# For manual CLI: export the variables defined in deployment-config.yaml
# Example (default config): SSH_USERNAME, SSH_PASSWORD, PPM_ADMIN_USER, PPM_ADMIN_PASSWORD
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
