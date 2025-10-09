# Key Concepts: PPM Deployment System

## Overview

This is a declarative, opinionated deployment system for OpenText PPM entity migration. It is built on a few core principles:
- **Single BOM-driven deployments** - All deployments are defined in a single, version-controlled YAML file (`boms/deployment.yaml`).
- **Baseline-first execution** - The pipeline guarantees that foundational 'baseline' entities are deployed before 'functional' business logic.
- **Static, Reusable GitLab CI/CD** - A simple, clear pipeline orchestrates deployments by triggering a reusable, staged workflow.
- **Manual, Manifest-based Rollback** - Every deployment is archived, but rollbacks are a deliberate, manual action performed via the CLI.
- **Mock-first Testing** - The system can be tested locally without a real PPM server.

---

## Core Components

### 1. **The Unified Bill of Materials (BOM)**
A single YAML manifest (`boms/deployment.yaml`) that defines an entire deployment event.
- **Shared Configuration:** Defines the `source_server` and `target_server` at the top level.
- **Deployment Sections:** Contains optional `baseline` and `functional` sections.
- **Control Flags:** Each section has an `enabled` flag to control whether it runs.
- **Rollback Path:** Each section can specify a `rollback_pipeline_id` for production environments.

**Example (`boms/deployment.yaml`):**
```yaml
version: "3.0.0"
change_request: "CR-12345"
created_by: "dev-team"

# Shared server configuration
source_server: dev-ppm-useast
target_server: test-ppm-useast

# Baseline section (optional)
baseline:
  enabled: true
  profile: baseline
  description: "Initial entity sync."
  rollback_pipeline_id: 12344

# Functional section (optional)
functional:
  enabled: true
  profile: functional-cd
  description: "Deploy new incident workflow."
  rollback_pipeline_id: 12345
  entities:
    - entity_id: 9
      reference_code: "WF_INCIDENT_MGMT"
```

### 2. **Profiles**
Define deployment behavior via structured flags (`profiles/*.yaml`):
- **`baseline.yaml`** - Broadly syncs foundational entities (Add Missing = Y).
- **`functional-cd.yaml`** - Deploys specific business logic on an existing baseline (Add Missing = N).

### 3. **Deployment Script (`deploy.py`)**
The single orchestrator for all actions, used by both the pipeline and users.
- **Staged Commands:** `extract`, `import`, `archive` for the CI/CD pipeline.
- **One-Shot Command:** `deploy` for convenient local end-to-end execution.
- **Rollback Command:** `rollback` for manual rollback operations.

### 4. **GitLab Pipeline**
A simple, two-stage pipeline defined in `.gitlab-ci.yml`:
- **`validate`:** Validates the `boms/deployment.yaml` file against all governance rules.
- **`deploy`:** Triggers a reusable child pipeline (`templates/gitlab-ci-template.yml`) for the `baseline` and/or `functional` sections if they are enabled. The `needs` keyword ensures the baseline deployment always runs first.

---

## Deployment & Rollback Strategy

### **Deployment Workflow**
The promotion process is now managed by editing the single BOM file.
1.  **Create Feature Branch:** Create a new branch for your change.
2.  **Edit `boms/deployment.yaml`:**
    *   Set the `source_server` and `target_server`.
    *   Ensure the desired section (`baseline` or `functional`) has `enabled: true`.
    *   Add entities to the `functional` section if needed.
3.  **Commit & Create Merge Request:** The pipeline runs automatically. It validates the BOM and then runs the enabled deployments in the correct order.
4.  **Promote:** To promote to the next environment (e.g., from `test` to `staging`), you merge, pull, and simply update the `target_server` in `boms/deployment.yaml` on the promotion branch.

### **Rollback Strategy (Manual)**
Rollback is a deliberate CLI action, not part of the automated pipeline.
1.  **Configure `deployment.yaml`:** In the section you want to roll back, set `rollback_pipeline_id` to either:
    *   A **numeric ID** from a previous GitLab pipeline.
    *   The keyword **`local`** to use the artifacts from your last local `deploy` run.
2.  **Run Command:** Execute the `rollback` command from your terminal, providing the necessary credentials.
    ```bash
    python3 tools/deploy.py rollback --type functional --bom boms/deployment.yaml
    ```
The script downloads the archived artifacts (bundles and original flags) and redeploys them to the target server.