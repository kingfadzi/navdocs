# PPM Deployment Configuration

This repository contains a declarative, opinionated configuration system for deploying OpenText PPM entities. It uses a single Bill of Materials (`BOM`) file to drive a reusable GitLab CI/CD pipeline, ensuring deployments are consistent, validated, and repeatable.

## Structure

```
.
├── .gitlab/
│   └── merge_request_templates/
├── archives/                      # Deployment archives (gitignored)
├── boms/
│   └── deployment.yaml            # SINGLE source of truth for all deployments
├── config/
│   ├── deployment-config.yaml     # Infrastructure config (servers, scripts)
│   └── rules.yaml                 # Governance rules for validation
├── mock/                          # Mock scripts for local testing
├── profiles/
│   ├── baseline.yaml              # Profile for foundational entities
│   └── functional-cd.yaml         # Profile for business logic
├── templates/
│   └── gitlab-ci-template.yml     # Reusable child pipeline for deployment stages
├── tools/
│   ├── deploy.py                  # Main deployment orchestrator script
│   ├── flag_compiler.py           # Compiles profile flags to Y/N string
│   └── validate_bom.py            # BOM validation script
├── .gitlab-ci.yml                 # Main GitLab CI/CD pipeline orchestrator
└── ...
```

## How It Works

1.  **Define a Deployment:** You edit a single file, `boms/deployment.yaml`, to define what you want to deploy. This file has sections for `baseline` and `functional` deployments, which can be enabled or disabled.
2.  **Commit and Push:** When you commit changes to this file, a GitLab pipeline is triggered.
3.  **Validation:** The pipeline's first stage validates your `deployment.yaml` against a set of governance rules (e.g., requires a rollback plan for prod, prevents deploying from prod to dev).
4.  **Staged Deployment:** If validation passes, the pipeline triggers a reusable workflow for each enabled section (`baseline` first, then `functional`). This workflow executes three distinct stages: `extract`, `import`, and `archive`.
5.  **Archiving:** Every successful deployment is archived, creating a deployment package and a manifest that can be used for manual rollbacks.

## Setup

```bash
# Install dependencies (one time)
python3 -m pip install PyYAML --break-system-packages

# Set credentials for local runs
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password
```

## Usage

The entire workflow is driven by the `boms/deployment.yaml` file.

### **1. Edit `boms/deployment.yaml`**

To create a deployment, edit the single BOM file. You can enable one or both sections.

```yaml
version: "3.0.0"
change_request: "CR-12345"
created_by: "dev-team"

# Shared server configuration for all deployments
source_server: dev-ppm-useast
target_server: test-ppm-useast

# --- BASELINE DEPLOYMENT ---
baseline:
  enabled: true # Set to 'false' to disable this section
  profile: baseline
  description: "Baseline entity sync."
  rollback_pipeline_id: 12344

# --- FUNCTIONAL DEPLOYMENT ---
functional:
  enabled: true # Set to 'false' to disable this section
  profile: functional-cd
  description: "Deploy new incident workflow."
  rollback_pipeline_id: 12345
  entities:
    - entity_id: 9
      reference_code: "WF_INCIDENT_MGMT"
      entity_type: "Workflow"
```

### **2. Validate Locally (Recommended)**

Before committing, validate your BOM against the project's rules:
```bash
python3 tools/validate_bom.py --file boms/deployment.yaml --branch <your-branch-name>
```

### **3. Run a Full Deployment Locally (Optional)**

For local testing, use the `deploy` command to run the entire `extract -> import -> archive` sequence.
```bash
# Run a full baseline deployment
python3 tools/deploy.py deploy --type baseline --bom boms/deployment.yaml

# Run a full functional deployment
python3 tools/deploy.py deploy --type functional --bom boms/deployment.yaml
```

### **4. Create a Merge Request**

Commit the changes to `boms/deployment.yaml` and push your branch. The pipeline will run automatically, validating and deploying the enabled sections.

## Manual Rollback

Rollback is a manual process that can be run against artifacts from GitLab or a previous local deployment.

1.  **Configure `deployment.yaml`:** In the section you want to roll back (`baseline` or `functional`), set `rollback_pipeline_id` to:
    *   A **GitLab Pipeline ID** (e.g., `12345`) to restore a version from a specific pipeline.
    *   The keyword **`local`** to restore the version from your last local `deploy` run.

2.  **Run the Rollback Command:**
    ```bash
    # Set credentials for the PPM server
    export PPM_USERNAME=your_username
    export PPM_PASSWORD=your_password

    # IF USING A GITLAB ID, also set these variables:
    export GITLAB_API_TOKEN=your_gitlab_token
    export CI_PROJECT_ID=your_project_id
    export CI_API_V4_URL="https://gitlab.company.com/api/v4"

    # Run the rollback command for the desired type
    python3 tools/deploy.py rollback --type functional --bom boms/deployment.yaml
    ```