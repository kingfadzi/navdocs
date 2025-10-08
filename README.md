# PPM Deployment Configuration

Declarative, opinionated configuration for OpenText PPM entity migration.

## Structure

```
.
├── .gitlab/
│   └── merge_request_templates/
│       └── Deployment.md          # MR template for deployments
├── profiles/
│   ├── baseline.yaml              # Baseline entity profile
│   └── functional-cd.yaml         # Business logic deployment profile
├── boms/                          # Bill of Materials for releases (flat structure)
├── config/
│   ├── deployment-config.yaml     # Infrastructure config (servers, scripts)
│   └── rules.yaml                 # Governance rules for validation
├── mock/                          # Mock scripts for testing
│   ├── kMigratorExtract.sh        # Mock PPM extract
│   └── kMigratorImport.sh         # Mock PPM import
├── tools/
│   ├── ppm-flag-schema.yaml       # Canonical 25-flag definitions (immutable)
│   ├── flag_compiler.py           # Compiles structured flags to Y/N string
│   ├── validate_bom.py            # BOM validation script (CI/CD)
│   └── deploy.py                  # Main deployment orchestrator
│   └── rollback.py                # Rollback orchestrator
├── .gitlab-ci.yml                 # GitLab CI/CD pipeline
├── .gitignore                     # Git ignore rules
├── CODEOWNERS                     # Required approvers per file
├── bundles/                       # Temporary bundle storage (gitignored)
└── archives/                      # Deployment archives (gitignored)
```

## Profiles

### baseline.yaml
- **Purpose**: Establish or sync foundational entities
- **When**: Initial environment setup OR periodic alignment
- **Entities**: Object Types, Request Headers, Validations, Commands, Environments
- **Philosophy**: Drift is normal - Add Missing = Y

### functional-cd.yaml
- **Purpose**: Continuous deployment of business logic
- **When**: Daily/frequent deployments after baseline exists
- **Entities**: Workflows, Request Types, Reports, Dashboards, Templates
- **Philosophy**: Baseline must exist - Add Missing = N

## Setup

```bash
# Install dependencies (one time)
python3 -m pip install PyYAML --break-system-packages

# Set PPM credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Verify setup with mock scripts
python3 tools/deploy.py baseline-repave --bom boms/baseline-dev-to-test.yaml
```

## Configuration

Edit `config/deployment-config.yaml` to configure:
- **Script paths** (mock or real kMigrator scripts)
- **Server registry** (server URLs, env types, regions)

```yaml
# kMigrator script paths
kmigrator:
  extract_script: "./mock/kMigratorExtract.sh"
  import_script: "./mock/kMigratorImport.sh"
  # For production: "/opt/ppm/bin/kMigratorExtract.sh"

# Deployment settings
deployment:
  bundle_dir: "./bundles"
  archive_dir: "./archives"

# PPM Server Registry (format: {env_type}-ppm-{region})
servers:
  dev-ppm-useast:
    url: "https://ppm-dev.company.com"
    env_type: dev
    credential_path: "/secrets/ppm-dev"
    region: useast

  test-ppm-useast:
    url: "https://ppm-test.company.com"
    env_type: test
    credential_path: "/secrets/ppm-test"
    region: useast

  prod-ppm-useast:
    url: "https://ppm-prod.company.com"
    env_type: prod
    credential_path: "/secrets/ppm-prod"
    region: useast
```

## Governance Rules

Deployment rules are defined in `config/rules.yaml` and automatically enforced during validation.

**Critical Rules (enabled by default):**
1. **Prohibited deployment paths** - Prevents reverse flow (prod→dev/test) and lateral flow (test→dev)
2. **Prod rollback requirement** - Production deployments must specify `rollback_pipeline_id`
3. **Prod change request** - Production deployments must specify `change_request`
4. **Different servers** - Source and target servers must be different
5. **Functional entities** - Functional BOMs must have non-empty `entities[]`

**Rule configuration** (`config/rules.yaml`):
```yaml
prohibited_deployment_paths:
  enabled: true
  paths:
    - source: prod
      target: [dev, test, uat, staging]
      reason: "Cannot copy production data to lower environments"

require_prod_rollback:
  enabled: true
  applies_to: [prod, staging]

require_entities_functional:
  enabled: true
```

Rules can be enabled/disabled individually by editing `config/rules.yaml`.

---

## Usage

### Baseline Repave
Deploy ALL baseline entities (full sync). Use for initial setup or periodic alignment.

**Edit baseline BOM:**
```bash
vim boms/baseline.yaml
```

```yaml
version: "1.0.0"
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
description: "Quarterly baseline alignment Q4 2025"
created_by: "ops-team"

# Optional metadata
# change_request: "OPS-12345"
# approved_by: "john.doe"
```

**Run deployment:**
```bash
# Set credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Deploy using BOM
python3 tools/deploy.py baseline-repave --bom boms/baseline.yaml
```

**What it does:**
- Reads source/target from BOM
- Extracts ALL entities from 7 baseline types (entity list from profile)
- Compiles flags from profile specified in BOM
- Imports to target with "Replace Existing = Y" and "Add Missing = Y"
- Creates deployment archive (bundles + BOM + flags + manifest)
- Creates rollback manifest for GitLab artifact-based rollback
- Cleans up temporary files

---

### Functional Release
Deploy SPECIFIC functional entities (selective). Use for sprint releases and feature deployments.

**Edit functional BOM:**
```bash
vim boms/functional.yaml
```

```yaml
version: "2.0.0"
change_request: "CR-54321"
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
description: "Sprint 42 - Incident workflow enhancements"
created_by: "platform-team"

entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
    entity_type: "Workflow"
    description: "Incident management approval workflow"

  - entity_id: 19
    reference_code: "RT_INCIDENT"
    entity_type: "Request Type"
    description: "Incident request form"

# Rollback to previous version
# rollback_pipeline_id: 12345  # Pipeline ID from previous successful deployment
```

**Run deployment:**
```bash
# Set credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Deploy using BOM
python3 tools/deploy.py functional-release --bom boms/functional.yaml
```

**What it does:**
- Reads source/target from BOM
- Extracts SPECIFIC entities by reference code (from BOM entity list)
- Compiles flags from profile specified in BOM
- Imports to target with "Replace Existing = Y" and "Add Missing = N"
- Creates deployment archive (bundles + BOM + flags + manifest)
- Creates rollback manifest for GitLab artifact-based rollback
- Cleans up temporary files

---

### Rollback Deployment
Restore a previous deployment using archived artifacts from GitLab.

**Prerequisites:**
- Previous deployment was successful and archived to GitLab artifacts
- BOM has `rollback_pipeline_id` field pointing to GitLab pipeline

**Edit functional.yaml for rollback:**
```bash
vim boms/functional.yaml
```

```yaml
version: "1.9.0-rollback"
change_request: "CR-54321-ROLLBACK"
profile: functional-cd
target_server: test-ppm-useast
description: "Rollback Sprint 42 deployment"
created_by: "ops-team"

# Rollback to previous version (copy from GitLab pipeline URL)
rollback_pipeline_id: 12345  # Pipeline ID from previous successful deployment
```

**Run rollback:**
```bash
# Set credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password
export GITLAB_API_TOKEN=your_gitlab_token  # Or use CI_JOB_TOKEN in CI

# Rollback using BOM
python3 tools/deploy.py rollback --bom boms/functional.yaml
```

**What it does:**
- Reads `rollback_pipeline_id` from BOM
- Downloads deployment archive from GitLab artifacts using API
- Extracts bundles and original deployment flags
- Imports bundles to target using original flags (exact rollback)
- Cleans up temporary files

**Note:** Rollback uses the exact flags from the original deployment, ensuring consistent behavior.

---

### Utilities

**Compile flags manually:**
```bash
python3 tools/flag_compiler.py baseline
# Output: YYYYYNNNNYYYYYNNNNNNNNNNN

python3 tools/flag_compiler.py functional-cd
# Output: NYNNNYYYYNNNYNYYYYYYYYYYN
```

## How It Works

1. Orchestrator reads profile (e.g., `profiles/baseline.yaml`)
2. Flag compiler converts structured flags to 25-character string
3. Extract entities listed in profile from source environment
4. Import to target with compiled flags
5. Log results

## Deployment Philosophy

### Baseline vs Functional

| Aspect | Baseline Repave | Functional Release |
|--------|----------------|-------------------|
| **Entities** | ALL baseline types | SPECIFIC entities by reference code |
| **Frequency** | Quarterly / on-demand | Weekly / per sprint |
| **Purpose** | Align infrastructure | Deploy business logic changes |
| **Add Missing** | YES (drift expected) | NO (baseline must exist) |
| **BOM Required** | Yes (source/target) | Yes (source/target/entities) |
| **Example** | Object Types, Validations | Workflows, Request Types, Reports |

### Drift Strategy

**Baseline drift:** Actively corrected - "Add Missing = Y" handles evolution
**Functional drift:** Tolerated - Selective deployment accepts missing entities over time

## Design Principles

✓ **Opinionated** - Two deployment types, no overrides
✓ **Declarative** - Configuration as code
✓ **Version controlled** - All configs in Git
✓ **Idempotent** - Safe to run repeatedly
✓ **Testable** - Mock scripts for CI/CD
✓ **Error-proof** - No manual flag strings

## GitLab CI/CD Pipeline

### **Pipeline Overview**

Automated deployment pipeline using `tools/deploy.py` with approval gates.

**Stages:**
1. **Validate** - BOM schema and required fields validation
2. **Review** - Manual review of BOM content (prod only)
3. **Deploy** - Run `deploy.py` (extract → import → archive)

### **Branching & Approval Strategy**

| Branch | Deploys To | MR Approvals | Pipeline Gate | Total Gates |
|--------|------------|--------------|---------------|-------------|
| `feature/*` | Dev | 2 | None | 2 |
| `develop` | Test | 2 | None | 2 |
| `main` | Prod | 3+ | Manual review | 4+ |

### **BOM Organization**

**Two static BOM files** - edit in place for deployments:

```
boms/
├── baseline.yaml      # Baseline deployments (infrastructure sync)
└── functional.yaml    # Functional deployments (features/fixes)
```

**Pipeline only watches these two files.** No other BOMs will trigger deployments.

### **Deployment Workflow**

#### **1. Edit BOM** (Feature Branch)
```bash
# Create feature branch
git checkout -b feature/CR-12345-incident-workflow

# Edit functional BOM
vim boms/functional.yaml
```

**Update functional.yaml:**
```yaml
version: "1.0.0"
change_request: "CR-12345"
profile: functional-cd
source_server: dev-ppm-useast
target_server: dev-ppm-useast  # Set to dev for feature branches
description: "Incident workflow enhancements"
created_by: "platform-team"

entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
    entity_type: "Workflow"
```

**Validate locally:**
```bash
python3 tools/validate_bom.py --file boms/functional.yaml --branch feature/CR-12345

# Test deployment (optional)
export PPM_USERNAME=testuser
export PPM_PASSWORD=testpass
python3 tools/deploy.py functional-release --bom boms/functional.yaml
```

#### **2. Create MR** (Dev Deployment)
```bash
# Commit and push
git add boms/functional.yaml
git commit -m "Deploy CR-12345 incident workflow to dev"
git push origin feature/CR-12345-incident-workflow

# Create MR to develop
# Request 2 approvals
```

**Pipeline runs:**
- Validate → Deploy to dev

#### **3. Promote to Test**
```bash
# Merge to develop
git checkout develop
git pull

# Edit same BOM, change target
vim boms/functional.yaml
# Change: target_server: test-ppm-useast

# Commit and push
git add boms/functional.yaml
git commit -m "Promote CR-12345 to test"
git push

# Auto-deploys to test (no MR needed if on develop)
```

**Pipeline runs:**
- Validate → Deploy to test

#### **4. Promote to Prod**
```bash
# Merge to main
git checkout main
git pull

# Edit same BOM, add rollback artifact
vim boms/functional.yaml
# Change: target_server: prod-ppm-useast
# Add: rollback_pipeline_id: 12345 (from test deployment pipeline)

# Commit and create MR to main
git add boms/functional.yaml
git commit -m "Deploy CR-12345 to prod"
git push

# MR to main requires 3+ approvals
```

**Pipeline runs:**
- Validate → **Manual Review** → Deploy to prod

**Approver reviews:**
1. Check BOM content in MR (entities, reference codes)
2. Verify rollback_pipeline_id is specified
3. Confirm change request is approved
4. Click "Approve" to proceed with deployment

### **Rollback**

**Edit functional.yaml with rollback config:**
```bash
vim boms/functional.yaml
```

```yaml
version: "0.9.0-rollback"
change_request: "CR-12345-ROLLBACK"
profile: functional-cd
target_server: prod-ppm-useast
description: "Rollback incident workflow to v0.9.0"
created_by: "ops-team"

# Point to previous version pipeline
rollback_pipeline_id: 12300  # Pipeline ID from previous successful deployment

# No entities needed for rollback (uses pipeline artifacts)
```

**Deploy rollback:**
```bash
git add boms/functional.yaml
git commit -m "Rollback incident workflow to v0.9.0"
git push

# MR requires 3+ approvals for prod
# Pipeline: Validate → Manual Review → Rollback
```

### **Local Validation**

Before creating MR, validate BOM locally:

```bash
# Validate BOM schema and governance rules
python3 tools/validate_bom.py --file boms/functional.yaml --branch feature/test

# Test deployment with mock scripts
export PPM_USERNAME=testuser
export PPM_PASSWORD=testpass
python3 tools/deploy.py functional-release --bom boms/functional.yaml
```

### **Pipeline Variables** (GitLab CI/CD Settings)

Configure in GitLab → Settings → CI/CD → Variables:

| Variable | Scope | Type | Protected | Masked |
|----------|-------|------|-----------|--------|
| `PPM_USERNAME` | dev | Variable | No | No |
| `PPM_PASSWORD` | dev | Variable | No | Yes |
| `PPM_USERNAME` | test | Variable | Yes | No |
| `PPM_PASSWORD` | test | Variable | Yes | Yes |
| `PPM_USERNAME` | prod | Variable | Yes | No |
| `PPM_PASSWORD` | prod | Variable | Yes | Yes |

---

## References

- [OpenText PPM kMigrator Documentation](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm) - Official flag definitions and script reference
