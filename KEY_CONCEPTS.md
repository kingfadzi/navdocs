# Key Concepts: PPM Deployment System

## Overview

This is a declarative, opinionated deployment system for OpenText PPM entity migration. It is built on a few core principles:
- **Two-BOM deployment system** - Deployments are defined in two separate, version-controlled YAML files (`boms/baseline.yaml` and `boms/functional.yaml`).
- **File-based triggering** - GitLab CI/CD uses the `changes:` keyword to trigger deployments only when specific BOM files are modified.
- **Baseline-first execution** - When both files change, the pipeline guarantees that foundational 'baseline' entities are deployed before 'functional' business logic.
- **Static, Reusable GitLab CI/CD** - A simple, clear pipeline orchestrates deployments by triggering a reusable, staged workflow.
- **Manual, Manifest-based Rollback** - Every deployment is archived, but rollbacks are a deliberate, manual action performed via the CLI.
- **Mock-first Testing** - The system can be tested locally without a real PPM server.

---

## Core Components

### 1. **Separate Baseline and Functional BOMs**
Two independent YAML files define deployments, each triggered by changes to their respective file.

**Baseline BOM (`boms/baseline.yaml`)**
- Deploys ALL foundational entities (defined by the baseline profile)
- No entity list needed - profile determines what gets deployed
- Triggered when `boms/baseline.yaml` is modified

**Example:**
```yaml
version: "1.0.0"
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
created_by: "ops-team"
description: "Quarterly baseline alignment"

# rollback_pipeline_id: 12344  # Optional: Pipeline ID to rollback to
```

**Functional BOM (`boms/functional.yaml`)**
- Deploys SPECIFIC business logic entities (listed explicitly)
- Requires entity list with IDs and reference codes
- Triggered when `boms/functional.yaml` is modified

**Example:**
```yaml
version: "2.0.0"
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
created_by: "dev-team"
description: "Deploy new incident workflow"

# rollback_pipeline_id: 12345  # Optional: Pipeline ID to rollback to

entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
    entity_type: "Workflow"
    description: "Incident management workflow"
```

### 2. **Profiles**

Profiles define deployment behavior through structured flag declarations that control which entity types are replaced and how dependencies are handled.

#### **What Profiles Do**
- Define which entity types to include in deployment
- Control dependency handling (add missing entities or require baseline)
- Specify entity IDs to extract for each deployment type
- Get compiled into 25-character Y/N flag strings for kMigrator

#### **Profile Structure**

Each profile contains:
1. **Metadata** - Name and description
2. **Flags** - Structured declarations for each entity type
   - `replace_*: true/false` - Include or skip this entity type
   - `add_missing_*: true/false` - Create missing dependencies or not
3. **Entities List** - Entity IDs and names to extract

**Example from `profiles/baseline.yaml`:**
```yaml
flags:
  replace_object_type: true      # Include Object Types
  replace_workflow: false        # Skip Workflows (not baseline)
  add_missing_environment: true  # Create missing environments

entities:
  - id: 26
    name: "Object Types"
    category: baseline
```

#### **Flag Compilation**

Structured flags are compiled to a 25-character Y/N string:
- `baseline.yaml` -> `YYYYYNNNNYYYYYNNNNNNNNNNN`
- `functional-cd.yaml` -> `NYYYYYNYYNNNYYYYYYYYYYN`

This string is passed to kMigrator scripts to control deployment behavior.

#### **Two Profiles**

**`baseline.yaml`** - Infrastructure Sync
- **Purpose:** Establish or sync foundational entities
- **Entity Types:** 7 infrastructure entities (Object Types, Validations, etc.)
- **Add Missing:** YES - Creates missing dependencies (drift correction)
- **Replace Mode:** YES for baseline entities, NO for functional
- **When to use:** Initial setup, quarterly alignment, infrastructure changes
- **Risk:** HIGH - Affects all downstream entities
- **Extract behavior:** Extracts ALL instances of each entity type (no filtering)

**`functional-cd.yaml`** - Business Logic Deployment
- **Purpose:** Deploy specific business logic entities
- **Entity Types:** 14 functional entities (Workflows, Request Types, Reports, etc.)
- **Add Missing:** NO - Requires baseline to exist first
- **Replace Mode:** NO for baseline entities, YES for functional
- **When to use:** Sprint releases, feature deployments, daily/weekly
- **Risk:** MEDIUM - Isolated to specific entities listed in BOM
- **Extract behavior:** Extracts ONLY entities listed in BOM's `entities[]` array

#### **Add Missing Philosophy**

**Baseline (`add_missing: true`):**
- Creates missing environments, security groups, request statuses
- Corrects drift proactively
- Safe for infrastructure sync where dependencies should exist everywhere

**Functional (`add_missing: false`):**
- Assumes baseline already exists in target
- Will fail if baseline dependencies missing
- Forces proper promotion order (baseline first, then functional)

### 3. **Deployment Orchestrator**
The deployment orchestrator (`tools.deployment.orchestrator`) is the single entry point for all deployment actions, used by both the pipeline and users.
- **Staged Commands:** `extract`, `import`, `archive` for the CI/CD pipeline.
- **One-Shot Command:** `deploy` for convenient local end-to-end execution.
- **Rollback Command:** `rollback` for manual rollback operations.
- **Vault Config:** `get-vault-config` for generating vault component includes.

### 4. **GitLab Pipeline**
A simple, two-stage pipeline defined in `.gitlab-ci.yml`:
- **`validate`:** Two separate validation jobs (`validate_baseline` and `validate_functional`) run when their respective BOM files change. Uses GitLab's `changes:` keyword to detect file modifications.
- **`deploy`:** Two separate deployment jobs (`deploy_baseline` and `deploy_functional`) trigger child pipelines. Each uses `changes:` to run only when its BOM file is modified. The `needs: [deploy_baseline]` with `optional: true` ensures baseline runs first when both files change.

### 5. **Tool Package Structure**

The deployment automation is organized into modular Python packages for maintainability:

```
tools/
├── config/           # Configuration, validation, and pipeline generation
│   ├── validation.py  # BOM validation and governance rules
│   ├── flags.py       # Profile flag compiler
│   └── pipeline.py    # GitLab CI child pipeline generator
├── deployment/       # Core deployment and orchestration
│   ├── orchestrator.py  # Main deployment orchestrator
│   ├── rollback.py      # Rollback operations
│   ├── utils.py         # Shared utilities
│   └── archive.py       # Archive and snapshot creation
├── executors/        # Command execution abstraction
│   ├── local.py       # Local executor (mock mode)
│   ├── remote.py      # Remote executor (SSH + S3)
│   └── ssh.py         # SSH connection handling
└── storage/          # Storage backend abstraction
    ├── base.py        # Storage interface
    ├── local.py       # Local filesystem storage
    └── s3.py          # S3/MinIO storage
```

**Invocation:**
- **Old format** (deprecated): `python3 tools/deploy.py`
- **New format** (current): `python3 -m tools.deployment.orchestrator`

All modules support both direct execution and package import for flexibility.

---

## Storage Backend Architecture

The system supports two storage modes for deployment bundles, selected via `deployment.storage_backend` in `config/deployment-config.yaml`:

### **Local Storage** (Development/Testing)
- **Use case:** Local development, testing without PPM servers
- **Configuration:** `storage_backend: "local"`
- **Bundle location:** `./bundles/` directory
- **Behavior:** No network transfer, bundles stay on local filesystem

### **S3/MinIO Storage** (Production)
- **Use case:** Production CI/CD with remote PPM servers
- **Configuration:** `storage_backend: "s3"`
- **Bundle location:** S3 bucket (e.g., `s3://ppm-deployment-bundles/bundles/`)
- **Credentials:** AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (from Vault)

**Bundle Flow in S3 Mode:**

**Extract Stage:**
```
PPM Server → SSH download to Runner → Upload to S3 → Download back for GitLab artifacts
```
- Why download back? Next stages (import/archive) need bundles as GitLab artifacts

**Import Stage:**
```
S3 → Download to Runner → SSH upload to PPM Server
```

**Archive Stage:**
```
Create archive ZIP → Upload to S3 → Copy to GitLab artifacts
```

**Key Point:** In S3 mode, bundles exist in THREE places:
1. S3 (permanent, for long-term rollback)
2. GitLab artifacts (temporary, for current pipeline stages)
3. S3 snapshots (complete deployment snapshot with manifest)

---

## Execution Modes

The system auto-selects between two execution modes based on configuration:

### **Local Executor** (Mock Mode)
- **Triggered when:** No `ssh_host` configured OR `storage_backend: "local"`
- **Use case:** Development, testing without real PPM
- **Behavior:**
  - Uses mock kMigrator scripts (`mock/kMigratorExtract.sh`, `mock/kMigratorImport.sh`)
  - Bundles stay on local filesystem
  - No SSH connections
  - Fast, safe for testing

**Setup:**
```yaml
# config/deployment-config.local.yaml
deployment:
  storage_backend: "local"
kmigrator:
  extract_script: "./mock/kMigratorExtract.sh"
  import_script: "./mock/kMigratorImport.sh"
```

```bash
export DEPLOYMENT_ENV=local
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

### **Remote Executor** (Production Mode)
- **Triggered when:** `ssh_host` configured AND `storage_backend: "s3"`
- **Use case:** Production CI/CD
- **Behavior:**
  - SSH to PPM servers to run real kMigrator scripts
  - Bundles stored in S3
  - Requires SSH credentials (from Vault)
  - Requires S3 credentials (from Vault)

**SSH Configuration:**
```yaml
servers:
  prod-ppm-useast:
    url: "https://ppm-prod.company.com"
    ssh_host: "ppm-prod.company.com"
    ssh_port: 22
    ssh_username_env: "PPM_SERVICE_ACCOUNT_USER"
    ssh_password_env: "PPM_SERVICE_ACCOUNT_PASSWORD"
```

**Auto-Selection Logic:**
```python
if ssh_host AND storage_backend == 's3':
    use RemoteExecutor (SSH + S3)
else:
    use LocalExecutor (mock scripts)
```

---

## Vault Integration & Secrets Management

Secrets are injected from HashiCorp Vault via GitLab CI/CD components.

### **Vault Component Providers**

The system supports pluggable vault components configured in `config/deployment-config.yaml`:

```yaml
vault_component_providers:
  standard:
    component_url: "eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve"
    component_version: "v1.0.3"
```

### **Per-Server Vault Roles**

Each server defines its vault role for credential retrieval:

```yaml
servers:
  dev-ppm-useast:
    url: "https://ppm-dev.company.com"
    vault_roles:
      - name: ppm-dev
        path: secret/data/ppm/dev/useast
```

**Exported Environment Variables:**
- `PPM_SERVICE_ACCOUNT_USER` - Service account username (for SSH and kMigrator)
- `PPM_SERVICE_ACCOUNT_PASSWORD` - Service account password (for SSH and kMigrator)

### **S3 Vault Configuration**

```yaml
s3:
  bucket_name: "ppm-deployment-bundles"
  vault_roles:
    - name: s3-read
      path: secret/data/shared/s3
```

**Exported Environment Variables:**
- `AWS_ACCESS_KEY_ID` - S3/MinIO access key
- `AWS_SECRET_ACCESS_KEY` - S3/MinIO secret key

### **Pipeline Workflow**

1. **Before job starts:** GitLab CI component fetches secrets from Vault
2. **Component exports:** Secrets as environment variables
3. **Job runs:** Deployment tools read credentials from environment
4. **After job:** Secrets are cleared automatically

**No credentials in code or config files!**

---

## Required Environment Variables

Production deployments require these environment variables (injected by Vault):

| Variable | Required For | Source | Example Value |
|----------|--------------|--------|---------------|
| `PPM_SERVICE_ACCOUNT_USER` | SSH authentication & kMigrator | Vault: `secret/data/ppm/{env}/useast` | `svc_kmigrator` |
| `PPM_SERVICE_ACCOUNT_PASSWORD` | SSH authentication & kMigrator | Vault: `secret/data/ppm/{env}/useast` | (secret) |
| `AWS_ACCESS_KEY_ID` | S3/MinIO storage | Vault: `secret/data/shared/s3` | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | S3/MinIO storage | Vault: `secret/data/shared/s3` | (secret) |
| `DEPLOYMENT_ENV` | Local testing override | Manual (local dev only) | `local` |

**Local Development:**
```bash
# For local testing without Vault
export DEPLOYMENT_ENV=local
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

**Production (CI/CD):**
- All credentials injected automatically by Vault component
- No manual export needed

---

## Local Testing Setup

The deployment system supports local testing without SSH or S3 using the **Local Executor** and configuration overrides.

### **Step 1: Create Local Configuration Override**

Create `config/deployment-config.local.yaml` to override production settings:

```yaml
# config/deployment-config.local.yaml
# Local development overrides (merged into deployment-config.yaml when DEPLOYMENT_ENV=local)

servers:
  dev-ppm-useast:
    url: "https://dev-ppm-useast.example.com:8443"
    ssh_host: null  # Disable SSH - use local executor
    ssh_username_env: null
    ssh_password_env: null

  test-ppm-useast:
    url: "https://test-ppm-useast.example.com:8443"
    ssh_host: null  # Disable SSH - use local executor
    ssh_username_env: null
    ssh_password_env: null

# Use local storage (no S3)
deployment:
  storage_backend: local

# Default credentials for kMigrator (uses local env vars)
default_credentials:
  ssh_username_env: PPM_USERNAME
  ssh_password_env: PPM_PASSWORD

# Local paths to mock kMigrator scripts
kmigrator:
  extract_script: "/path/to/local/kMigratorExtract.sh"
  import_script: "/path/to/local/kMigratorImport.sh"
```

**Key Points:**
- Set `ssh_host: null` to disable SSH and use Local Executor
- Set `storage_backend: local` to skip S3 and use local filesystem
- Use simple env var names (`PPM_USERNAME`, `PPM_PASSWORD`) instead of production vars
- This file is gitignored - safe for local credentials

### **Step 2: Set Local Environment Variables**

```bash
# Export local mode flag
export DEPLOYMENT_ENV=local

# Export PPM credentials (for kMigrator scripts)
export PPM_USERNAME=your_ppm_username
export PPM_PASSWORD=your_ppm_password

# Verify configuration will merge correctly
python3 -c "from tools.deployment.utils import load_config; import yaml; print(yaml.dump(load_config(), default_flow_style=False))"
```

### **Step 3: Mock kMigrator Scripts (Optional)**

For testing without actual PPM servers, create mock scripts:

```bash
#!/bin/bash
# mock/kMigratorExtract.sh
echo "Mock extract: $@"
echo "Creating mock bundle..."
echo '<?xml version="1.0"?><bundle><entity>Mock Entity</entity></bundle>' > /tmp/mock_bundle_$$.xml
echo "Bundle created: /tmp/mock_bundle_$$.xml"
exit 0
```

```bash
#!/bin/bash
# mock/kMigratorImport.sh
echo "Mock import: $@"
echo "Mock import successful"
exit 0
```

Update `deployment-config.local.yaml` to point to mock scripts:
```yaml
kmigrator:
  extract_script: "/path/to/mock/kMigratorExtract.sh"
  import_script: "/path/to/mock/kMigratorImport.sh"
```

### **Step 4: Run Local Deployment**

**Full Deployment (Extract → Import → Archive):**
```bash
export DEPLOYMENT_ENV=local
python3 -m tools.deployment.orchestrator deploy \
  --type functional \
  --bom boms/functional.yaml
```

**Individual Stages:**
```bash
# Extract only
export DEPLOYMENT_ENV=local
python3 -m tools.deployment.orchestrator extract \
  --type baseline \
  --bom boms/baseline.yaml

# Import only (after extract)
python3 -m tools.deployment.orchestrator import \
  --type baseline \
  --bom boms/baseline.yaml

# Archive only (after import)
python3 -m tools.deployment.orchestrator archive \
  --type baseline \
  --bom boms/baseline.yaml
```

### **Step 5: Verify Local Execution**

**Expected Behavior with Local Executor:**
```
==========================================================
PHASE 1: EXTRACT (FUNCTIONAL)
==========================================================
Source: dev-ppm-useast, Target: test-ppm-useast, Profile: functional-cd
Storage: LOCAL
Executor: LocalExecutor
Flags: NYNNNYYYYNNNYNYYYYYYYYYYN

Extracting 3 functional entities...

Executing: /path/to/kMigratorExtract.sh -username your_ppm_username -password *** -url https://dev-ppm-useast.example.com:8443 -action Bundle -entityId 9 -referenceCode WF_INCIDENT_MGMT

✓ Extracted 3 bundles for functional
Saved metadata: bundles/functional-metadata.yaml
```

**Key Indicators of Local Mode:**
- `Storage: LOCAL` (not S3)
- `Executor: LocalExecutor` (not RemoteExecutor)
- No SSH connection messages
- Bundles saved to `bundles/` directory (not uploaded to S3)

### **Step 6: Test Rollback Locally**

```bash
# After successful local deployment
export DEPLOYMENT_ENV=local

# Update BOM file with rollback_pipeline_id: local
# Then run rollback
python3 -m tools.deployment.orchestrator rollback \
  --type functional \
  --bom boms/functional.yaml
```

**Local Rollback Behavior:**
- Reads from `archives/` directory (no GitLab artifact download)
- Uses `ROLLBACK_MANIFEST.yaml` from last local deployment
- Redeploys bundles using original flags

### **Local Testing Workflow**

**Typical Development Cycle:**
```bash
# 1. Set local mode
export DEPLOYMENT_ENV=local
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# 2. Edit BOM file (e.g., add new workflow entity)
vim boms/functional.yaml

# 3. Validate BOM
python3 -m tools.config.validation --file boms/functional.yaml

# 4. Test deployment locally
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml

# 5. Verify archives created
ls -lh archives/
cat archives/ROLLBACK_MANIFEST.yaml

# 6. Test rollback
# Edit boms/functional.yaml: rollback_pipeline_id: local
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml

# 7. If everything works, commit and push
git add boms/functional.yaml
git commit -m "Add incident management workflow"
git push
```

### **Common Pitfalls**

**Error: "Missing PPM credentials"**
```
ERROR: PPM credentials not set
  Required: PPM_USERNAME and PPM_PASSWORD
```
**Solution:** Export environment variables before running:
```bash
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password
```

**Error: "SSH connection failed" (in local mode)**
```
ERROR: Could not establish SSH connection to dev-ppm-useast
```
**Solution:** Verify `deployment-config.local.yaml` has `ssh_host: null`:
```yaml
servers:
  dev-ppm-useast:
    ssh_host: null  # Must be null for local executor
```

**Error: "S3 bucket not configured" (in local mode)**
```
ERROR: S3 bucket 'ppm-deployment-snapshots' not accessible
```
**Solution:** Set storage backend to local in `deployment-config.local.yaml`:
```yaml
deployment:
  storage_backend: local  # Not s3
```

**Error: "Config file not found"**
```
FileNotFoundError: config/deployment-config.yaml
```
**Solution:** Run scripts from repository root directory:
```bash
cd /path/to/navdocs
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

### **Differences: Local vs Production**

| **Aspect** | **Local (DEPLOYMENT_ENV=local)** | **Production (CI/CD)** |
|------------|-----------------------------------|------------------------|
| **Executor** | LocalExecutor (direct execution) | RemoteExecutor (SSH + SCP) |
| **Storage** | Local filesystem (`bundles/`, `archives/`) | S3/MinIO (permanent retention) |
| **Credentials** | `PPM_USERNAME`, `PPM_PASSWORD` | Vault-injected (`PPM_SERVICE_ACCOUNT_*`) |
| **Configuration** | Merged: base + local override | Base only (`deployment-config.yaml`) |
| **kMigrator Location** | Local filesystem paths | Remote server paths |
| **Rollback Source** | Local `archives/` directory | GitLab artifacts → S3 → local |
| **Evidence Package** | Created locally | Uploaded to S3 + GitLab artifacts |
| **Best For** | Development, testing, BOM validation | Production deployments, rollback |

### **Advanced: Testing Remote Executor Locally**

To test SSH/S3 functionality without CI/CD:

```bash
# 1. Set local mode
export DEPLOYMENT_ENV=local

# 2. Configure ssh_host in deployment-config.local.yaml
servers:
  dev-ppm-useast:
    ssh_host: "dev-server.example.com"  # Enable SSH
    ssh_username_env: PPM_USERNAME
    ssh_password_env: PPM_PASSWORD

# 3. Configure S3 (MinIO local instance)
deployment:
  storage_backend: s3

storage:
  s3:
    endpoint_url: "http://localhost:9000"  # Local MinIO
    bucket_name: "test-deployments"

# 4. Export AWS credentials for local MinIO
export AWS_ACCESS_KEY_ID=minioadmin
export AWS_SECRET_ACCESS_KEY=minioadmin

# 5. Run deployment (will use RemoteExecutor + S3)
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

This allows testing the full production flow locally with SSH and S3 storage.

---

## Entity Categories

### **Baseline Entities** (Infrastructure)
Must be aligned across ALL environments before continuous deployment.

| **Entity** | **ID** | **What It Does** | **Why It Matters** | **Change Freq** |
|------------|--------|------------------|--------------------|-----------------|
| **Object Types** | **26** | Define structure and behavior of objects (requests, projects, packages) | Must match everywhere or request types/projects won't work correctly | Quarterly |
| **Request Header Types** | **39** | Define fields and layout for request forms | Baseline must be aligned so request types behave the same in every environment | Quarterly |
| **Validations** | **13** | Define lookup lists and rules for fields | Inconsistent validations cause requests to behave differently across environments | Monthly |
| **User Data Contexts** | **37** | Define shared user data for custom fields | Keep aligned so environment-specific data is consistent | Quarterly |
| **Special Commands** | **11** | Reusable backend functions called in workflows | Missing commands break workflow steps | As-needed |
| **Environments** | **4** | Logical deployment targets referenced in workflows | Missing environments cause package promotion failures | Rarely |
| **Environment Groups** | **58** | Logical deployment target groups | Missing groups cause package promotion failures | Rarely |

**Philosophy:** Drift is corrected proactively (Add Missing = Y during bootstrap, then N for drift detection)

**Critical Notes:**
- **Request Statuses** - Part of Request Header Types (Entity ID 39), controlled by Flag 12
- **Security Groups** - Referenced but NOT migrated automatically; must exist in all environments before workflow deployment

### **Functional Entities** (Business Logic)
Deploy frequently once baseline is stable.

| **Entity** | **ID** | **What It Does** | **Why It Matters** | **Change Freq** |
|------------|--------|------------------|--------------------|-----------------|
| **Workflows** | **9** | Define process flows for requests/projects | Core business logic; safely replaceable once baseline is in place | Weekly |
| **Request Types** | **19** | Define request forms + link to workflows | Core to business process; promote with replace once baseline is stable | Weekly |
| **Report Types** | **17** | Define parameterized reports | Frequently updated; safe to always replace | Weekly |
| **Overview Page Sections** | **61** | Define what appears on overview pages | Safe to promote whenever layout changes | Weekly |
| **Dashboard Modules** | **470** | Define dashboard pages & layouts | Safe to migrate continuously | Weekly |
| **Dashboard Data Sources** | **505** | SQL queries behind portlets | Versioned and replaceable | Weekly |
| **Portlet Definitions** | **509** | Define dashboard widgets | Can be promoted anytime; low risk if baseline is aligned | Weekly |
| **Project Types** | **521** | Define project templates, policies, lifecycle | Promote during process or template changes | Monthly |
| **Work Plan Templates** | **522** | Define standard project task breakdowns | Migrated when template changes are approved | Monthly |
| **Program Types** | **901** | Define program-level structure | Migrated when program governance changes | Monthly |
| **Portfolio Types** | **903** | Define portfolio containers and hierarchy | Supported entity; safe to promote | Monthly |
| **OData Data Sources** | **906** | Define OData-backed queries | Supported; **OData links are NOT migrated** | Monthly |
| **Custom Menu** | **907** | Define custom UI menu entries | UI extension; safe to promote | As-needed |
| **Chatbot Intent** | **908** | Define chatbot intents (PPM 25.2+) | Optional; for chatbot-enabled environments | As-needed |
| **PPM Integration SDK** | **9900** | Define PPM Integration SDK objects | Stable but script-supported; promote if used | Rarely |

**Philosophy:** Drift is tolerated (Add Missing = N, baseline handles dependencies)

**Critical Notes:**
- All functional entities require baseline to exist first (environments, statuses, security groups)
- OData Data Sources: Only the data source definition migrates; OData links must be manually configured
- Chatbot Intent: Requires Report Type flag (Flag 7 = Y) when deploying
- Portfolio Type: Requires Module flag (Flag 16 = Y) when deploying

### **Entity Reference Summary**

**Baseline vs Functional Decision:**

| **If the entity...** | **Then it's...** |
|----------------------|------------------|
| Changes break existing workflows/requests | **Baseline** |
| Defines foundational structure (object types, fields, validations) | **Baseline** |
| Is referenced by many other entities (environments, commands) | **Baseline** |
| Changes frequently (weekly) as business logic evolves | **Functional** |
| Can be replaced independently without breaking dependencies | **Functional** |
| Is specific to a single business process | **Functional** |

**Complete Entity ID Quick Reference:**
```
Baseline:  4, 11, 13, 26, 37, 39, 58
Functional: 9, 17, 19, 61, 470, 505, 509, 521, 522, 901, 903, 906, 907, 908, 9900
```

**See Also:**
- Complete kMigrator entity reference: `KMIGRATOR_REFERENCE.md`
- Flag compilation: `tools/config/flags.py`
- Profile definitions: `config/profiles/*.yaml`

---

## Governance Rules Engine

The system includes an automated rules engine that validates all BOM files before deployment. Rules are defined in `config/rules.yaml` and enforced by the BOM validator (`tools.config.validation`) during the validate stage.

### **Critical Rules (Enabled by Default)**

**1. Deployment Promotion Order**
- **Rule:** Deployments must follow strict sequential order: dev -> test -> staging -> prod
- **No skipping allowed:** Cannot deploy dev -> prod directly (must go through test and staging)
- **Severity:** Blocking
- **Why:** Ensures proper testing at each environment before production
- **Example violation:** Deploying from dev directly to prod

**2. Rollback Required (All Environments)**
- **Rule:** All deployments must specify `rollback_pipeline_id`
- **Applies to:** ALL environments (dev, test, staging, prod)
- **Severity:** Blocking
- **Why:** Enables instant recovery from deployment mistakes
- **Example violation:** BOM missing `rollback_pipeline_id` field

**3. Change Request Required (Prod/Staging)**
- **Rule:** Production and staging deployments must specify `change_request`
- **Applies to:** prod, staging
- **Severity:** Blocking
- **Why:** Ensures audit trail and change management compliance
- **Example violation:** Prod deployment missing `change_request: "CR-12345"`

**4. Source != Target**
- **Rule:** Source and target servers must be different
- **Severity:** Blocking
- **Why:** Prevents accidental self-deployment (deploying prod to itself)
- **Example violation:** `source_server: prod-ppm-useast`, `target_server: prod-ppm-useast`

**5. Branch-Environment Alignment**
- **Rule:** BOM `target_server` must match the branch's deployment environment
- **Severity:** Blocking
- **Why:** Prevents deploying to wrong environment from wrong branch
- **Mappings:**
  - `feature/*` branches -> can only deploy to `test`
  - `develop` branch -> can only deploy to `staging`
  - `main` branch -> can only deploy to `prod`
- **Example violation:** `feature/CR-123` branch trying to deploy to `prod`

### **How Rules Are Enforced**

1. **Before deployment:** `validate_bom.py` runs automatically in the validate stage
2. **Blocking behavior:** If any rule fails, deployment stops before extraction
3. **Clear errors:** Validation shows exactly which rule failed and why
4. **Local testing:** Run `python3 -m tools.config.validation --file boms/baseline.yaml --branch feature/test` before committing

### **Future Rules (Disabled - Enable When Ready)**

These rules exist in `config/rules.yaml` but are disabled by default:

- **max_entities_per_deployment** - Warn if deployment contains > 50 entities (easier troubleshooting)

Enable by setting `enabled: true` in `config/rules.yaml`

### **Rules Configuration**

All rules are defined in `config/rules.yaml` with:
- `enabled`: true/false - Turn rule on/off
- `severity`: blocking/warning - Stop deployment or just warn
- `applies_to`: List of environments where rule applies
- `message`: Error message shown when rule fails

**Example rule definition:**
```yaml
require_prod_change_request:
  enabled: true
  applies_to: [prod, staging]
  severity: blocking
  message: "Production deployments must specify change_request"
```

---

## Deployment & Rollback Strategy

### **Deployment Workflow**
The promotion process is managed by editing the appropriate BOM file(s).

1.  **Create Feature Branch:** Create a new branch for your change.

2.  **Edit the appropriate BOM file:**
    *   **For baseline deployments:** Edit `boms/baseline.yaml`
      - Set `source_server` and `target_server`
      - Update `description` and `change_request`
    *   **For functional deployments:** Edit `boms/functional.yaml`
      - Set `source_server` and `target_server`
      - Update `description` and `change_request`
      - Add/update entities in the `entities` list

3.  **Commit & Create Merge Request:** The pipeline runs automatically:
    - If you changed `baseline.yaml`, only baseline deployment runs
    - If you changed `functional.yaml`, only functional deployment runs
    - If you changed both files, baseline runs first, then functional

4.  **Promote:** To promote to the next environment (e.g., from `test` to `staging`):
    - Merge to the appropriate branch
    - Pull the latest changes
    - Update the `target_server` in the relevant BOM file(s)
    - Commit and push

### **Baseline Repave**
Deploy ALL baseline entity types (full sync).

* **When:** Initial setup, quarterly alignment, or on-demand
* **Scope:** All 7 baseline entity types
* **Flags:** Replace = Y, Add Missing = Y
* **Risk:** HIGH - affects all downstream entities
* **Approval:** 2 (non-prod), 3+ (prod) with platform team

**BOM Example (`boms/baseline.yaml`):**
```yaml
version: "1.0.0"
profile: baseline
source_server: prod-ppm-useast
target_server: test-ppm-useast
description: "Q4 2025 baseline alignment"
created_by: "ops-team"
```

### **Functional Release**
Deploy SPECIFIC functional entities (selective).

* **When:** Sprint releases, feature deployments
* **Scope:** Only entities listed in BOM
* **Flags:** Replace = Y, Add Missing = N
* **Risk:** MEDIUM - isolated to specific entities
* **Approval:** 2 (non-prod), 3+ (prod)

**BOM Example (`boms/functional.yaml`):**
```yaml
version: "2.0.0"
change_request: "CR-54321"
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
    entity_type: "Workflow"
# rollback_pipeline_id: 12345  # Pipeline ID from previous deployment
```

---

## Branching & Promotion Flow

### **Branch Strategy**

| Branch | Deploys To | MR Approvals | Pipeline Gate |
|--------|------------|--------------|---------------|
| `feature/*` | Test | 2 | None |
| `develop` | Staging | 2 | None |
| `main` | Prod | 3+ | Manual review |

### **Promotion Workflow**

```
1. Feature branch -> Edit boms/functional.yaml (target_server: test-ppm-useast)
   -> MR (2 approvals) -> Merge -> Auto-deploy to test

2. Promote to staging -> Edit boms/functional.yaml (target_server: staging-ppm-useast)
   -> MR to develop (2 approvals) -> Merge -> Auto-deploy to staging

3. Promote to prod -> Edit boms/functional.yaml (target_server: prod-ppm-useast)
   -> Add rollback_pipeline_id from previous successful deployment
   -> MR to main (3+ approvals) -> Manual review -> Deploy to prod
```

Each promotion updates `target_server` in the BOM for clear audit trail.

### **Rollback Strategy (Manual)**
Rollback is a deliberate CLI action, not part of the automated pipeline.

**Prerequisites:**
1. **Valid BOM File:** BOM must pass validation (schema, required fields, entity references)
2. **Rollback Pipeline ID:** Set `rollback_pipeline_id` in BOM to:
   - A **numeric ID** from a previous GitLab pipeline (e.g., `12345`)
   - The keyword **`local`** to use artifacts from your last local `deploy` run
3. **Approvals:** Same approval requirements as forward deployment (2 for non-prod, 3+ for prod)
4. **Archive Availability:** Rollback archive must exist in GitLab artifacts or S3 cold storage

**Rollback Command:**
```bash
# For baseline rollback
python3 -m tools.deployment.orchestrator rollback --type baseline --bom boms/baseline.yaml

# For functional rollback
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
```

### **Rollback Execution Flow**

The rollback process follows these steps in order:

1. **Validate BOM File** (FIRST STEP)
   - Verify BOM schema and required fields
   - Check `rollback_pipeline_id` is set and valid
   - Exit immediately if validation fails

2. **Determine Rollback Source**
   - If `rollback_pipeline_id = "local"`: Use local archives directory
   - If numeric pipeline ID: Use three-tier retrieval strategy

3. **Three-Tier Archive Retrieval Strategy**

   **Tier 1: GitLab Artifacts (Primary)**
   - Download artifacts from specified pipeline ID
   - Look for `ROLLBACK_MANIFEST.yaml` in artifacts
   - **Retention:** 1 year (configurable in .gitlab-ci.yml)
   - **Best for:** Recent deployments (within artifact retention period)

   **Tier 2: S3 Cold Storage (Fallback)**
   - If GitLab artifacts expired or unavailable, query S3
   - Use `s3_snapshot_url` from ROLLBACK_MANIFEST metadata
   - Download complete deployment snapshot from S3
   - **Retention:** Permanent (lifecycle policy configurable)
   - **Best for:** Long-term rollback needs (6+ months old)

   **Tier 3: Local Filesystem (Last Resort)**
   - If both GitLab and S3 unavailable, check local `archives/` directory
   - **Warning:** Only available if original deployment ran locally
   - **Best for:** Development/testing environments

4. **Locate Archive ZIP**
   - Read `ROLLBACK_MANIFEST.yaml` to find `rollback_bundle_path`
   - Verify archive file exists and is accessible

5. **Validate Target Server**
   - Compare manifest's `target_server` with BOM's `target_server`
   - **Safety check:** Prevents cross-environment rollback (e.g., prod archive → test)
   - Exit with error if mismatch detected

6. **Extract Archive Contents**
   - Unzip archive to temporary directory
   - Extract:
     - `bundles/*.xml` - Entity bundles to redeploy
     - `bom.yaml` - Original BOM configuration
     - `flags.txt` - Exact 25-character flag string from original deployment
     - `manifest.yaml` - Deployment metadata

7. **Import Bundles to Target Server**
   - Use **original flags** from `flags.txt` (ensures identical deployment behavior)
   - Redeploy all bundles in same order as original deployment
   - Use same i18n_mode and refdata_mode settings

8. **Cleanup Temporary Files**
   - Remove extracted archive contents
   - Keep ROLLBACK_MANIFEST.yaml for audit trail

### **Archive Structure on Success**

Every successful deployment creates artifacts stored in **both GitLab and S3** (production mode):

**1. Archive ZIP** (`archives/CR-12345-v1.0.0-20251007-archive.zip`)

Contains:
- `bundles/` - Extracted XML entity files
- `bom.yaml` - Original BOM file used for deployment
- `flags.txt` - Exact 25-character Y/N flag string used
- `manifest.yaml` - Deployment metadata (version, timestamp, bundles list)

**2. Evidence Package** (`archives/CR-12345-v1.0.0-20251007-evidence.zip`)

Contains:
- Archive ZIP (above)
- BOM file
- Deployment logs
- Git metadata (commit SHA, branch, pipeline ID)

**3. Rollback Manifest** (`archives/ROLLBACK_MANIFEST.yaml`)

**Version 2.0.0 Structure:**
```yaml
rollback_bundle_path: archives/CR-12345-v1.0.0-20251007-archive.zip
s3_snapshot_url: s3://ppm-deployment-snapshots/12345/functional-snapshot.tar.gz
s3_archive_url: s3://ppm-deployment-snapshots/12345/CR-12345-v1.0.0-20251007-archive.zip
storage_backend: s3
deployment_metadata:
  deployment_type: functional
  profile: functional-cd
  target_server: test-ppm-useast
  bom_version: "2.0.0"
  change_request: "CR-12345"
  flags: "NYNNNYYYYNNNYNYYYYYYYYYYN"
git_context:
  commit_sha: abc123def456
  pipeline_id: 54321
  branch: feature/incident-workflow
manifest_version: "2.0.0"
created_at: 2025-01-07T14:30:00Z
```

**New in v2.0.0:**
- `s3_snapshot_url` - Complete deployment snapshot in S3 (bundles + metadata + evidence)
- `s3_archive_url` - Direct S3 URL to archive ZIP for faster retrieval
- `storage_backend` - Indicates storage mode used (local or s3)

**Storage Locations:**
- **GitLab Artifacts:** 1 year retention (faster access for recent deployments)
- **S3 Cold Storage:** Permanent retention (long-term rollback capability)
- **Local Filesystem:** Development/testing only

**Purpose:**
- **Archive ZIP** - Contains bundles and exact deployment configuration for rollback
- **Evidence Package** - Complete audit trail for compliance and troubleshooting
- **ROLLBACK_MANIFEST.yaml** - Index file pointing to archive locations (GitLab + S3)

### **Error Scenarios and Troubleshooting**

**BOM Validation Failures:**
```
ERROR: BOM validation failed
- Missing required field: rollback_pipeline_id
- Invalid target_server: not found in deployment-config.yaml
```
**Solution:** Fix BOM file errors before proceeding with rollback

**Archive Not Found (GitLab):**
```
WARNING: GitLab artifacts not available for pipeline 12345
Reason: Artifacts expired (older than 1 year)
Falling back to S3 cold storage...
```
**Solution:** System automatically falls back to S3 if configured

**Archive Not Found (S3):**
```
ERROR: S3 snapshot not available
s3_snapshot_url: s3://ppm-deployment-snapshots/12345/functional-snapshot.tar.gz
Reason: NoSuchKey
```
**Solution:** Check if deployment was run with storage_backend=local or S3 bucket access

**Target Server Mismatch:**
```
ERROR: Target server mismatch detected
BOM target_server: prod-ppm-useast
Manifest target_server: test-ppm-useast
SAFETY CHECK: Cannot rollback test archive to production
```
**Solution:** Verify you're using correct BOM and rollback_pipeline_id

**Key Rollback Principles:**
- Rollback uses **exact flags** from original deployment for consistency
- Three-tier retrieval ensures rollback capability even after GitLab artifact expiration
- Target server validation prevents accidental cross-environment rollback
- ROLLBACK_MANIFEST v2.0.0 provides dual-location redundancy (GitLab + S3)

---

## Approval Gates & CODEOWNERS

### **Approval Matrix**

| Deployment | Environment | MR Approvals | Pipeline Gate | Total |
|------------|-------------|--------------|---------------|-------|
| Functional | Test | 2 | None | 2 |
| Functional | Staging | 2 | None | 2 |
| Functional | Prod | 3+ | Manual | 4+ |
| Baseline | Test | 2 | None | 2 |
| Baseline | Staging | 2 (+ platform) | None | 2 |
| Baseline | Prod | 3+ (+ platform) | Manual | 4+ |

### **CODEOWNERS**
- Baseline BOMs (`boms/baseline.yaml`) -> `@platform-team` required
- Prod deployments (when `target_server` contains "prod") -> `@tech-leads` + `@ops-team` required
- Profiles/schemas (`profiles/*.yaml`, `profiles/ppm-flag-schema.yaml`) -> `@platform-team` required

---

## Key Design Principles

* **Opinionated** - Two deployment types (baseline/functional), no overrides
* **Declarative** - BOMs are version-controlled, reviewed via MR
* **Idempotent** - Same BOM = same result (safe to rerun)
* **Testable** - Mock scripts work without real PPM
* **Lean** - Reuses orchestrator for local and CI/CD
* **Traceable** - Git commits + GitLab artifacts = full audit trail

---

## Benefits

### **For Platform Engineers:**
- No manual flag strings (compiled from profiles)
- No manual kMigrator commands (automated by orchestrator)
- Instant rollback (download from GitLab artifacts, redeploy)

### **For Operations:**
- Clear approval gates (2 or 3+ depending on environment)
- BOM review before deployment (see exactly what will change)
- Audit trail (Git history + GitLab artifacts)

### **For Developers:**
- Test locally with mock scripts (no PPM needed)
- Same tooling for dev/test/prod (consistency)
- Fast feedback (automated deployments)

---

## Common Scenarios

### **Initial Setup (New Environment)**
1. Run baseline repave to establish foundation
2. Test functional deployment with sample workflow
3. Enable continuous deployment

### **Sprint Release (Functional Changes)**
1. Create feature branch, edit `boms/functional.yaml`
2. Set `target_server: test-ppm-useast` and add entities
3. Create MR -> 2 approvals -> auto-deploy to test
4. Update `target_server: staging-ppm-useast` -> MR to develop -> auto-deploy to staging
5. Update `target_server: prod-ppm-useast`, add `rollback_pipeline_id` -> MR to main -> 3+ approvals + manual gate -> deploy to prod

### **Quarterly Baseline Sync**
1. Platform team edits `boms/baseline.yaml`
2. Set `target_server: test-ppm-useast` -> test in test environment
3. Update `target_server: staging-ppm-useast` -> test in staging
4. Update `target_server: prod-ppm-useast` -> schedule prod deployment (off-hours)
5. Requires 3+ approvals including platform team

### **Emergency Rollback**
1. Edit appropriate BOM file (`baseline.yaml` or `functional.yaml`)
2. Set `rollback_pipeline_id` to previous successful pipeline ID
3. Get expedited approvals (same as forward: 3+ for prod)
4. Deploy (fast: no extraction needed, uses archived bundles)

---

## References

- [OpenText PPM kMigrator Documentation](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm)
- [Semantic Versioning](https://semver.org/)
- [GitLab CI/CD](https://docs.gitlab.com/ee/ci/)