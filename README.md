# PPM Deployment Configuration

This repository contains a declarative, opinionated configuration system for deploying OpenText PPM entities. It uses two separate Bill of Materials (`BOM`) files - one for baseline entities and one for functional entities - to drive a reusable GitLab CI/CD pipeline, ensuring deployments are consistent, validated, and repeatable.

## Structure

```
.
├── .gitlab-ci.yml                     # Main pipeline orchestrator
├── archives/                          # Deployment archives (gitignored)
├── boms/
│   ├── baseline.yaml                  # Baseline deployment BOM
│   └── functional.yaml                # Functional deployment BOM
├── config/
│   ├── deployment-config.yaml         # Production server/storage config
│   ├── deployment-config.local.yaml   # Local overrides (gitignored)
│   └── rules.yaml                     # Governance rules
├── profiles/
│   ├── baseline.yaml                  # Baseline entity profile
│   └── functional-cd.yaml             # Functional entity profile
├── templates/
│   └── child-pipeline-template.yml    # Reusable CI/CD stages
├── tools/
│   ├── config/                        # Configuration & validation
│   │   ├── flags.py                   # Flag compiler
│   │   ├── validation.py              # BOM validator
│   │   └── pipeline.py                # Pipeline generator
│   ├── deployment/                    # Core deployment logic
│   │   ├── orchestrator.py            # Main deployment orchestrator
│   │   ├── archive.py                 # Archive & evidence creation
│   │   ├── rollback.py                # Rollback execution
│   │   └── utils.py                   # Shared utilities
│   ├── executors/                     # Execution abstraction
│   │   ├── local.py                   # Local executor (development)
│   │   └── ssh.py                     # Remote executor (production)
│   └── storage/                       # Storage backends
│       ├── local.py                   # Local filesystem
│       └── s3.py                      # S3/MinIO storage
├── KEY_CONCEPTS.md                    # Comprehensive system documentation
├── KMIGRATOR_REFERENCE.md             # kMigrator script/flag reference
└── README.md                          # This file
```

## How It Works

1.  **Define a Deployment:** You edit either `boms/baseline.yaml` or `boms/functional.yaml` (or both) to define what you want to deploy.
    - **baseline.yaml** - Deploys ALL foundational entities (Object Types, Validations, Commands, etc.)
    - **functional.yaml** - Deploys SPECIFIC business logic entities (Workflows, Request Types, Reports, etc.)

2.  **Commit and Push:** When you commit changes to one or both BOM files, a GitLab pipeline is triggered. The pipeline detects which files changed and runs only the relevant deployments.

3.  **Validation:** The pipeline validates the changed BOM file(s) against governance rules (e.g., requires rollback plan for prod, prevents deploying from prod to dev).

4.  **Staged Deployment:** If validation passes, the pipeline triggers a child workflow for each changed BOM:
    - If only `baseline.yaml` changed → runs baseline deployment
    - If only `functional.yaml` changed → runs functional deployment
    - If both files changed → runs baseline first, then functional

    Each workflow executes three stages: `extract`, `import`, and `archive`.

5.  **Archiving:** Every successful deployment is archived, creating a deployment package and manifest that can be used for manual rollbacks.

6.  **Storage Backends:**
    - **Local Mode** (development): Bundles stored in `bundles/` and `archives/` directories
    - **S3 Mode** (production): Bundles uploaded to S3 for permanent retention, downloaded to GitLab artifacts

7.  **Execution Modes:**
    - **Local Executor**: Direct script execution on local machine (development/testing)
    - **Remote Executor**: SSH + SCP to remote PPM servers (production)

## Setup

### **Production (CI/CD)**
No setup required - credentials injected automatically by HashiCorp Vault via GitLab CI/CD component.

### **Local Development**

**1. Install Dependencies:**
```bash
python3 -m pip install PyYAML --break-system-packages
```

**2. Create Local Configuration Override:**
```bash
cp config/deployment-config.yaml config/deployment-config.local.yaml
# Edit deployment-config.local.yaml:
# - Set ssh_host: null (use local executor)
# - Set storage_backend: local (skip S3)
# - Update kmigrator script paths to local paths
```

**3. Set Environment Variables:**
```bash
export DEPLOYMENT_ENV=local          # Enable local mode
export PPM_USERNAME=your_username    # PPM credentials
export PPM_PASSWORD=your_password
```

**See [KEY_CONCEPTS.md - Local Testing Setup](KEY_CONCEPTS.md#local-testing-setup) for complete configuration guide.**

## Usage

The workflow is driven by two BOM files: `boms/baseline.yaml` and `boms/functional.yaml`.

### **1. Edit the Appropriate BOM File**

**For Baseline Deployments** - Edit `boms/baseline.yaml`:

```yaml
version: "1.0.0"
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
created_by: "ops-team"
description: "Quarterly baseline alignment"

# rollback_pipeline_id: 12344  # Optional: for rollback
```

**For Functional Deployments** - Edit `boms/functional.yaml`:

```yaml
version: "2.0.0"
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
created_by: "dev-team"
description: "Deploy new incident workflow"

# rollback_pipeline_id: 12345  # Optional: for rollback

entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
    entity_type: "Workflow"
    description: "Incident management workflow"
```

**Deployment Modes:**
- **Local Mode** (`DEPLOYMENT_ENV=local`): Uses LocalExecutor + local storage
- **Production Mode** (CI/CD): Uses RemoteExecutor + S3 storage with Vault credentials

### **2. Validate Locally (Recommended)**

Before committing, validate your BOM file(s):

```bash
# Validate baseline BOM
python3 -m tools.config.validation --file boms/baseline.yaml --branch <your-branch-name>

# Validate functional BOM
python3 -m tools.config.validation --file boms/functional.yaml --branch <your-branch-name>
```

### **3. Run a Full Deployment Locally (Optional)**

For local testing, use the `deploy` command to run the entire `extract → import → archive` sequence:

```bash
# Run a full baseline deployment
python3 -m tools.deployment.orchestrator deploy --type baseline --bom boms/baseline.yaml

# Run a full functional deployment
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

### **4. Create a Merge Request**

Commit the changes and push your branch. The pipeline will run automatically:
- Changed `baseline.yaml`? → Baseline deployment runs
- Changed `functional.yaml`? → Functional deployment runs
- Changed both files? → Baseline runs first, then functional

## CLI Reference

Complete reference for all deployment automation commands.

### **Deployment Commands**

#### `deploy` - Full Deployment (Extract → Import → Archive)

Run the complete deployment sequence in one command.

```bash
python3 -m tools.deployment.orchestrator deploy \
  --type {baseline|functional} \
  --bom <bom-file>
```

**Parameters:**
- `--type` - Deployment type: `baseline` or `functional` (required)
- `--bom` - Path to BOM file (required)

**Examples:**
```bash
# Full baseline deployment
python3 -m tools.deployment.orchestrator deploy --type baseline --bom boms/baseline.yaml

# Full functional deployment
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

**What it does:**
1. Validates BOM file
2. Extracts entities from source server
3. Imports entities to target server
4. Creates archive and evidence package
5. Uploads to S3 (production mode) or saves locally (local mode)

---

#### `extract` - Phase 1: Extract Entities

Extract entities from source server and create XML bundles.

```bash
python3 -m tools.deployment.orchestrator extract \
  --type {baseline|functional} \
  --bom <bom-file>
```

**Parameters:**
- `--type` - Deployment type: `baseline` or `functional` (required)
- `--bom` - Path to BOM file (required)

**Examples:**
```bash
# Extract baseline entities
python3 -m tools.deployment.orchestrator extract --type baseline --bom boms/baseline.yaml

# Extract functional entities
python3 -m tools.deployment.orchestrator extract --type functional --bom boms/functional.yaml
```

**What it does:**
1. Reads BOM configuration
2. Calls kMigratorExtract.sh for each entity
3. Creates XML bundle files
4. Saves metadata to `bundles/{type}-metadata.yaml`
5. (S3 mode) Uploads bundles to S3 and downloads to GitLab artifacts

**Output:**
- Bundles stored in `bundles/` directory (local mode) or S3 (production mode)
- Metadata file: `bundles/{type}-metadata.yaml`

---

#### `import` - Phase 2: Import Entities

Import XML bundles to target server.

```bash
python3 -m tools.deployment.orchestrator import \
  --type {baseline|functional} \
  --bom <bom-file>
```

**Parameters:**
- `--type` - Deployment type: `baseline` or `functional` (required)
- `--bom` - Path to BOM file (required)

**Examples:**
```bash
# Import baseline entities
python3 -m tools.deployment.orchestrator import --type baseline --bom boms/baseline.yaml

# Import functional entities
python3 -m tools.deployment.orchestrator import --type functional --bom boms/functional.yaml
```

**Prerequisites:**
- Extract phase must be completed first
- Metadata file must exist: `bundles/{type}-metadata.yaml`

**What it does:**
1. Reads metadata from extract phase
2. Calls kMigratorImport.sh for each bundle
3. Uses compiled flags from profile
4. Imports entities to target server

---

#### `archive` - Phase 3: Archive Deployment

Create deployment archive and evidence package.

```bash
python3 -m tools.deployment.orchestrator archive \
  --type {baseline|functional} \
  --bom <bom-file>
```

**Parameters:**
- `--type` - Deployment type: `baseline` or `functional` (required)
- `--bom` - Path to BOM file (required)

**Examples:**
```bash
# Archive baseline deployment
python3 -m tools.deployment.orchestrator archive --type baseline --bom boms/baseline.yaml

# Archive functional deployment
python3 -m tools.deployment.orchestrator archive --type functional --bom boms/functional.yaml
```

**Prerequisites:**
- Extract and import phases must be completed first

**What it does:**
1. Creates archive ZIP with bundles, BOM, flags, manifest
2. Creates evidence package with archive + logs + git metadata
3. Creates ROLLBACK_MANIFEST.yaml (v2.0.0)
4. (S3 mode) Uploads complete snapshot to S3
5. (S3 mode) Updates ROLLBACK_MANIFEST with S3 URLs
6. Prints rollback instructions

**Output:**
- Archive: `archives/CR-{change_request}-v{version}-{date}-archive.zip`
- Evidence: `archives/CR-{change_request}-v{version}-{date}-evidence.zip`
- Manifest: `archives/ROLLBACK_MANIFEST.yaml`
- (S3 mode) Complete snapshot in S3

---

#### `rollback` - Restore Previous Deployment

Rollback to a previous deployment using three-tier retrieval.

```bash
python3 -m tools.deployment.orchestrator rollback \
  --type {baseline|functional} \
  --bom <bom-file>
```

**Parameters:**
- `--type` - Deployment type: `baseline` or `functional` (required)
- `--bom` - Path to BOM file with `rollback_pipeline_id` set (required)

**Examples:**
```bash
# Rollback baseline to pipeline 12345
# (First set rollback_pipeline_id: 12345 in boms/baseline.yaml)
python3 -m tools.deployment.orchestrator rollback --type baseline --bom boms/baseline.yaml

# Rollback functional to last local deployment
# (First set rollback_pipeline_id: local in boms/functional.yaml)
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
```

**Prerequisites:**
- BOM file must have `rollback_pipeline_id` set
- Archive must exist in GitLab artifacts, S3, or local filesystem

**What it does:**
1. Validates BOM file (checks rollback_pipeline_id is set)
2. Retrieves archive (GitLab → S3 → local fallback)
3. Validates target server matches
4. Extracts bundles and original flags
5. Redeploys using exact flags from original deployment

**See [Manual Rollback](#manual-rollback) section for detailed guide.**

---

#### `get-vault-config` - Get Vault Configuration

Extract Vault configuration for CI/CD setup.

```bash
python3 -m tools.deployment.orchestrator get-vault-config \
  --server <server-name>
```

**Parameters:**
- `--server` - Server name from deployment-config.yaml (required)

**Examples:**
```bash
# Get Vault config for dev-ppm-useast
python3 -m tools.deployment.orchestrator get-vault-config --server dev-ppm-useast

# Get Vault config for prod-ppm-useast
python3 -m tools.deployment.orchestrator get-vault-config --server prod-ppm-useast
```

**What it does:**
- Reads server configuration from `config/deployment-config.yaml`
- Extracts `ci_vault_configs` value for specified server
- Prints raw vault configuration string (for GitLab CI/CD variables)

**Use case:** Setting up vault configuration in GitLab CI/CD variables.

---

### **Validation Commands**

#### `validate` - Validate BOM File

Validate BOM file against governance rules.

```bash
python3 -m tools.config.validation \
  --file <bom-file> \
  [--branch <branch-name>]
```

**Parameters:**
- `--file` - Path to BOM file (required)
- `--branch` - Git branch name for environment detection (optional)

**Examples:**
```bash
# Validate baseline BOM
python3 -m tools.config.validation --file boms/baseline.yaml

# Validate functional BOM with branch context
python3 -m tools.config.validation --file boms/functional.yaml --branch feature/incident-workflow

# Validate before committing
python3 -m tools.config.validation --file boms/baseline.yaml --branch main
```

**Validation checks:**
- BOM schema (required fields, data types)
- Entity references (entity_id, reference_code, entity_type)
- Server configuration (source/target exist in deployment-config.yaml)
- Governance rules from `config/rules.yaml`:
  - Rollback plan required for production
  - Prevent deploying from prod to dev
  - Change request format validation
  - Custom rules

**Exit codes:**
- `0` - Validation passed
- `1` - Validation failed

---

### **Configuration Commands**

#### `flags` - Compile Profile Flags

Compile profile YAML to 25-character Y/N flag string.

```bash
python3 -m tools.config.flags <profile-name>
```

**Parameters:**
- `<profile-name>` - Profile name (e.g., `baseline`, `functional-cd`)

**Examples:**
```bash
# Compile baseline profile flags
python3 -m tools.config.flags baseline
# Output: YNYYYNNNNYYYNYYYYNNNNNNN

# Compile functional-cd profile flags
python3 -m tools.config.flags functional-cd
# Output: NYNNNYYYYNNNYNYYYYYYYYYYN
```

**What it does:**
1. Reads profile from `config/profiles/{profile-name}.yaml`
2. Compiles 25 flag values (yes/no) to Y/N string
3. Outputs 25-character string for kMigratorImport.sh

**See [KMIGRATOR_REFERENCE.md](KMIGRATOR_REFERENCE.md) for complete flag reference.**

---

#### `pipeline` - Generate Dynamic Pipeline

Generate GitLab child pipeline YAML based on changed BOM files.

```bash
# Typically called by GitLab CI/CD, not manually
CI_COMMIT_BRANCH=<branch-name> python3 -m tools.config.pipeline
```

**Environment Variables:**
- `CI_COMMIT_BRANCH` - Git branch name (required)

**Examples:**
```bash
# Generate pipeline for main branch
CI_COMMIT_BRANCH=main python3 -m tools.config.pipeline

# Generate pipeline for feature branch
CI_COMMIT_BRANCH=feature/new-workflow python3 -m tools.config.pipeline
```

**What it does:**
1. Detects which BOM files changed (baseline.yaml, functional.yaml)
2. Generates child pipeline YAML with appropriate stages
3. Outputs to `.gitlab/dynamic-child-pipeline.yml`

**Output scenarios:**
- Only `baseline.yaml` changed → baseline deployment pipeline
- Only `functional.yaml` changed → functional deployment pipeline
- Both changed → baseline deployment, then functional deployment
- Neither changed → validation-only pipeline

---

### **Environment Variables**

These environment variables control deployment behavior:

| Variable | Purpose | Values | Default |
|----------|---------|--------|---------|
| `DEPLOYMENT_ENV` | Enable local mode | `local` or unset | (unset) |
| `PPM_USERNAME` | PPM service account username | string | (required) |
| `PPM_PASSWORD` | PPM service account password | string | (required) |
| `PPM_SERVICE_ACCOUNT_USER` | Production PPM username (Vault) | string | (Vault-injected) |
| `PPM_SERVICE_ACCOUNT_PASSWORD` | Production PPM password (Vault) | string | (Vault-injected) |
| `AWS_ACCESS_KEY_ID` | S3/MinIO access key | string | (Vault-injected) |
| `AWS_SECRET_ACCESS_KEY` | S3/MinIO secret key | string | (Vault-injected) |
| `CI_PIPELINE_ID` | GitLab pipeline ID | number | (GitLab-injected) |
| `CI_COMMIT_BRANCH` | Git branch name | string | (GitLab-injected) |

**Local development:**
```bash
export DEPLOYMENT_ENV=local
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password
```

**Production (CI/CD):**
- All credentials automatically injected by Vault component
- No manual configuration needed

---

### **Common Command Sequences**

#### **Local Testing Workflow**
```bash
# 1. Set local mode
export DEPLOYMENT_ENV=local
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# 2. Validate BOM
python3 -m tools.config.validation --file boms/functional.yaml

# 3. Run full deployment
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml

# 4. Test rollback (set rollback_pipeline_id: local in BOM first)
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
```

#### **CI/CD Stage Commands** (from child-pipeline-template.yml)
```bash
# Extract stage
python3 -m tools.deployment.orchestrator extract --type $DEPLOYMENT_TYPE --bom $BOM_FILE

# Import stage (depends on extract)
python3 -m tools.deployment.orchestrator import --type $DEPLOYMENT_TYPE --bom $BOM_FILE

# Archive stage (depends on import)
python3 -m tools.deployment.orchestrator archive --type $DEPLOYMENT_TYPE --bom $BOM_FILE
```

#### **Manual Phase-by-Phase Deployment**
```bash
# Phase 1: Extract entities
python3 -m tools.deployment.orchestrator extract --type baseline --bom boms/baseline.yaml

# Phase 2: Import entities
python3 -m tools.deployment.orchestrator import --type baseline --bom boms/baseline.yaml

# Phase 3: Archive deployment
python3 -m tools.deployment.orchestrator archive --type baseline --bom boms/baseline.yaml
```

---

## Manual Rollback

Rollback uses a **three-tier retrieval strategy** to restore previous deployments:

**Retrieval Priority:**
1. **GitLab Artifacts** (primary) - 1 year retention, fastest access
2. **S3 Cold Storage** (fallback) - Permanent retention for long-term rollback
3. **Local Filesystem** (development) - Last resort for local testing

### **Rollback Process:**

**1. BOM Validation (First Step)**
- Rollback validates BOM before proceeding
- Checks `rollback_pipeline_id` is set and valid
- Exits immediately if validation fails

**2. Configure BOM File**

Set `rollback_pipeline_id` in the BOM file you want to rollback:
```yaml
# boms/functional.yaml
rollback_pipeline_id: 12345  # GitLab pipeline ID
# OR
rollback_pipeline_id: local  # Use last local deployment
```

**3. Run Rollback Command**

```bash
# Set local mode and credentials
export DEPLOYMENT_ENV=local
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Baseline rollback
python3 -m tools.deployment.orchestrator rollback --type baseline --bom boms/baseline.yaml

# Functional rollback
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
```

**Rollback Behavior:**
- Downloads archive from GitLab artifacts or S3
- Validates target server matches (prevents cross-environment rollback)
- Extracts bundles and original flags
- Redeploys using **exact flags** from original deployment

**See [KEY_CONCEPTS.md - Rollback Strategy](KEY_CONCEPTS.md#rollback-strategy-manual) for detailed execution flow and troubleshooting.**

## Architecture

This deployment system uses:

- **Storage Backends**: Local filesystem (dev) or S3/MinIO (prod) with permanent retention
- **Execution Modes**: Local executor (direct) or Remote executor (SSH + SCP)
- **Secrets Management**: HashiCorp Vault via GitLab CI/CD component
- **Package Structure**: Modular tools package (`tools.deployment`, `tools.config`, `tools.storage`, `tools.executors`)

**For detailed architecture:**
- [KEY_CONCEPTS.md](KEY_CONCEPTS.md) - Comprehensive system documentation
- [KMIGRATOR_REFERENCE.md](KMIGRATOR_REFERENCE.md) - kMigrator script and flag reference

## Documentation

### **[KEY_CONCEPTS.md](KEY_CONCEPTS.md)**
Complete system documentation including:
- BOM structure and profiles
- Tool package structure
- Storage backends (local vs S3)
- Execution modes (local vs remote)
- Vault integration and secrets management
- Entity categories (baseline vs functional)
- Rollback strategy with three-tier retrieval
- Local testing setup with step-by-step guide
- Deployment pipeline flow
- Governance rules engine

### **[KMIGRATOR_REFERENCE.md](KMIGRATOR_REFERENCE.md)**
kMigrator technical reference:
- kMigratorExtract.sh complete parameter reference
- kMigratorImport.sh complete parameter reference
- All 25 import flags with baseline vs functional usage
- Entity ID reference table with categories
- Flag compilation system explanation
- Common deployment scenarios
- Troubleshooting guide