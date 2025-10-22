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

### 3. **Deployment Script (`deploy.py`)**
The single orchestrator for all actions, used by both the pipeline and users.
- **Staged Commands:** `extract`, `import`, `archive` for the CI/CD pipeline.
- **One-Shot Command:** `deploy` for convenient local end-to-end execution.
- **Rollback Command:** `rollback` for manual rollback operations.

### 4. **GitLab Pipeline**
A simple, two-stage pipeline defined in `.gitlab-ci.yml`:
- **`validate`:** Two separate validation jobs (`validate_baseline` and `validate_functional`) run when their respective BOM files change. Uses GitLab's `changes:` keyword to detect file modifications.
- **`deploy`:** Two separate deployment jobs (`deploy_baseline` and `deploy_functional`) trigger child pipelines. Each uses `changes:` to run only when its BOM file is modified. The `needs: [deploy_baseline]` with `optional: true` ensures baseline runs first when both files change.

---

## Entity Categories

### **Baseline Entities** (Infrastructure)
Must be aligned across ALL environments before continuous deployment.

| Entity | Entity ID | Risk | Change Frequency |
|--------|-----------|------|------------------|
| Object Types | 26 | HIGH | Quarterly |
| Request Header Types | 39 | HIGH | Quarterly |
| Validations | 13 | MEDIUM | Monthly |
| User Data Contexts | 37 | MEDIUM | Quarterly |
| Special Commands | 11 | MEDIUM | As-needed |
| Environments | 4 | LOW | Rarely |
| Environment Groups | 58 | LOW | Rarely |

**Philosophy:** Drift is corrected proactively (Add Missing = Y)

### **Functional Entities** (Business Logic)
Deploy frequently once baseline is stable.

| Entity | Entity ID | Risk | Change Frequency |
|--------|-----------|------|------------------|
| Workflows | 9 | MEDIUM | Weekly |
| Request Types | 19 | MEDIUM | Weekly |
| Report Types | 17 | LOW | Weekly |
| Overview Page Sections | 61 | LOW | Weekly |
| Dashboard Modules | 470 | LOW | Weekly |
| Dashboard Data Sources | 505 | LOW | Weekly |
| Portlet Definitions | 509 | LOW | Weekly |
| Project Types | 521 | MEDIUM | Monthly |
| Work Plan Templates | 522 | LOW | Monthly |
| Program Types | 901 | MEDIUM | Monthly |
| Portfolio Types | 903 | MEDIUM | Monthly |
| OData Data Sources | 906 | LOW | Monthly |
| Custom Menu | 907 | LOW | As-needed |
| PPM Integration SDK | 9900 | HIGH | Rarely |

**Philosophy:** Drift is tolerated (Add Missing = N, baseline handles dependencies)

---

## Governance Rules Engine

The system includes an automated rules engine that validates all BOM files before deployment. Rules are defined in `config/rules.yaml` and enforced by `validate_bom.py` during the validate stage.

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
4. **Local testing:** Run `python3 tools/validate_bom.py --file boms/baseline.yaml --branch feature/test` before committing

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

1.  **Configure the appropriate BOM file:** Set `rollback_pipeline_id` to either:
    *   A **numeric ID** from a previous GitLab pipeline (e.g., `12345`)
    *   The keyword **`local`** to use the artifacts from your last local `deploy` run

2.  **Run the rollback command:**
    ```bash
    # For baseline rollback
    python3 tools/deploy.py rollback --type baseline --bom boms/baseline.yaml

    # For functional rollback
    python3 tools/deploy.py rollback --type functional --bom boms/functional.yaml
    ```

The script downloads the archived artifacts (bundles and original flags) and redeploys them to the target server.

### **Archive on Success**
Every successful deployment creates two artifacts stored in GitLab:

**1. Archive ZIP** (`archives/CR-12345-v1.0.0-20251007-archive.zip`)

Contains:
- `bundles/` - Extracted XML files
- `bom.yaml` - Original BOM file
- `flags.txt` - Exact flags used (25-char Y/N string)
- `manifest.yaml` - Deployment metadata (version, timestamp, bundles list)

**2. Rollback Manifest** (`archives/ROLLBACK_MANIFEST.yaml`)
```yaml
rollback_bundle_path: archives/CR-12345-v1.0.0-20251007-archive.zip
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
manifest_version: "1.0.0"
created_at: 2025-01-07T14:30:00Z
```

Both artifacts stored in GitLab pipeline artifacts (prod: 1 year retention)

**Purpose:**
- **Archive ZIP** - Contains bundles and original deployment configuration
- **ROLLBACK_MANIFEST.yaml** - Points to the archive and provides metadata for validation

### **Rollback Execution Flow**

1. **Configure Rollback:** Set `rollback_pipeline_id` in BOM to previous successful pipeline ID
2. **Approval:** Get same approvals as forward deployment (2 for non-prod, 3+ for prod)
3. **Download Artifacts:** Pipeline downloads artifacts from GitLab (includes ROLLBACK_MANIFEST.yaml + archive ZIP)
4. **Locate Archive:** Read `ROLLBACK_MANIFEST.yaml` to find `rollback_bundle_path`
5. **Validate Target:** Compare manifest's `target_server` with BOM's `target_server`
   - **Safety check:** Prevents accidental cross-environment rollback (e.g., prod archive -> test)
   - Exits with error if mismatch detected
6. **Extract Archive:** Unzip the archive and read `flags.txt` for original deployment flags
7. **Import Bundles:** Redeploy all bundles using **original flags** from the archive
8. **Cleanup:** Remove temporary files

**Key Points:**
- Rollback uses exact flags from original deployment for consistency
- Target server validation prevents deploying wrong archive to wrong environment
- ROLLBACK_MANIFEST.yaml is the "index" that makes rollback fast and safe

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
- Profiles/schemas (`profiles/*.yaml`, `tools/ppm-flag-schema.yaml`) -> `@platform-team` required

---

## Key Design Principles

* **Opinionated** - Two deployment types (baseline/functional), no overrides
* **Declarative** - BOMs are version-controlled, reviewed via MR
* **Idempotent** - Same BOM = same result (safe to rerun)
* **Testable** - Mock scripts work without real PPM
* **Lean** - Reuses `deploy.py` for local and CI/CD
* **Traceable** - Git commits + GitLab artifacts = full audit trail

---

## Benefits

### **For Platform Engineers:**
- No manual flag strings (compiled from profiles)
- No manual kMigrator commands (automated by deploy.py)
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