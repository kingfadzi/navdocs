# PPM Deployment Configuration

This repository contains a declarative, opinionated configuration system for deploying OpenText PPM entities. It uses two separate Bill of Materials (`BOM`) files - one for baseline entities and one for functional entities - to drive a reusable GitLab CI/CD pipeline, ensuring deployments are consistent, validated, and repeatable.

## Structure

```
.
- .gitlab/
  - merge_request_templates/
- archives/                      # Deployment archives (gitignored)
- boms/
  - baseline.yaml                # Baseline deployment configuration
  - functional.yaml              # Functional deployment configuration
- config/
  - deployment-config.yaml       # Infrastructure config (servers, scripts)
  - rules.yaml                   # Governance rules for validation
- mock/                          # Mock scripts for local testing
- profiles/
  - baseline.yaml                # Profile for foundational entities
  - functional-cd.yaml           # Profile for business logic
- templates/
  - gitlab-ci-template.yml       # Reusable child pipeline for deployment stages
- tools/
  - deploy.py                    # Main deployment orchestrator script
  - flag_compiler.py             # Compiles profile flags to Y/N string
  - validate_bom.py              # BOM validation script
- .gitlab-ci.yml                 # Main GitLab CI/CD pipeline orchestrator
- ...
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

## Setup

```bash
# Install dependencies (one time)
python3 -m pip install PyYAML --break-system-packages

# Set credentials for local runs
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password
```

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

Rollback is a manual process that can be run against artifacts from GitLab or a previous local deployment.

1.  **Configure the appropriate BOM file:** Set `rollback_pipeline_id` in the file you want to rollback:
    *   A **GitLab Pipeline ID** (e.g., `12345`) to restore a version from a specific pipeline
    *   The keyword **`local`** to restore the version from your last local `deploy` run

2.  **Run the Rollback Command:**

    ```bash
    # Set credentials for the PPM server
    export PPM_USERNAME=your_username
    export PPM_PASSWORD=your_password

    # IF USING A GITLAB ID, also set these variables:
    export GITLAB_API_TOKEN=your_gitlab_token
    export CI_PROJECT_ID=your_project_id
    export CI_API_V4_URL="https://gitlab.company.com/api/v4"

    # Run the rollback command for the desired deployment type
    # For baseline rollback:
    python3 -m tools.deployment.orchestrator rollback --type baseline --bom boms/baseline.yaml

    # For functional rollback:
    python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
    ```