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