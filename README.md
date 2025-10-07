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
├── boms/                          # Bill of Materials for releases
│   ├── baseline/
│   └── functional/
│       ├── dev/
│       ├── test/
│       └── prod/
├── config/
│   └── deployment-config.yaml     # All configuration (scripts, environments, Nexus)
├── mock/                          # Mock scripts for testing
│   ├── kMigratorExtract.sh        # Mock PPM extract
│   └── kMigratorImport.sh         # Mock PPM import
├── tools/
│   ├── ppm-flag-schema.yaml       # Canonical 25-flag definitions (immutable)
│   ├── flag_compiler.py           # Compiles structured flags to Y/N string
│   ├── nexus_client.py            # Mock Nexus client (local file operations)
│   ├── validate_bom.py            # BOM validation script (CI/CD)
│   └── deploy.py                  # Main deployment orchestrator
├── .gitlab-ci.yml                 # GitLab CI/CD pipeline
├── .gitignore                     # Git ignore rules
├── CODEOWNERS                     # Required approvers per file
├── bundles/                       # Temporary bundle storage (gitignored)
├── archives/                      # Deployment archives (gitignored)
└── nexus-storage/                 # Mock Nexus storage (gitignored)
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
python3 tools/deploy.py baseline-repave --bom boms/baseline-prod-to-test.yaml
```

**Note:** Nexus is mocked using local file operations in `nexus-storage/` directory. No external server required.

## Configuration

Edit `config/deployment-config.yaml` to configure:
- **Script paths** (mock or real kMigrator scripts)
- **Environment URLs** (dev, test, prod)
- **Nexus repository** (mocked locally, stores in `nexus-storage/`)

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

# Mock Nexus (uses local nexus-storage/ directory)
nexus:
  url: "http://localhost:8081"  # Ignored in mock
  repository: "ppm-deployments"
  subfolder: "2025"

# PPM environments
environments:
  dev:
    url: "https://ppm-dev.company.com"
  test:
    url: "https://ppm-test.company.com"
  prod:
    url: "https://ppm-prod.company.com"
```

## Usage

### Baseline Repave
Deploy ALL baseline entities (full sync). Use for initial setup or periodic alignment.

**Create a baseline BOM** (`boms/baseline-prod-to-test.yaml`):
```yaml
profile: baseline
source_environment: prod
target_environment: test

# Metadata (optional, for future use)
# created_by: "ops-team"
# change_request: "CR-12345"
# description: "Quarterly baseline alignment"
```

**Run deployment:**
```bash
# Set credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Deploy using BOM
python3 tools/deploy.py baseline-repave --bom boms/baseline-prod-to-test.yaml
```

**What it does:**
- Reads source/target from BOM
- Extracts ALL entities from 7 baseline types (entity list from profile)
- Compiles flags from profile specified in BOM
- Imports to target with "Replace Existing = Y" and "Add Missing = Y"
- Creates deployment archive (bundles + BOM + flags + manifest)
- Pushes archive to Nexus for rollback capability
- Cleans up temporary files

---

### Functional Release
Deploy SPECIFIC functional entities (selective). Use for sprint releases and feature deployments.

**Create a functional BOM** (`boms/release-2025.10.yaml`):
```yaml
profile: functional-cd
source_environment: dev
target_environment: test

entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"

  - entity_id: 19
    reference_code: "RT_INCIDENT"

# Metadata (optional, for future use)
# created_by: "dev-team"
# change_request: "CR-54321"
# jira_ticket: "PROJ-1234"
# description: "Sprint 42 release"
```

**Run deployment:**
```bash
# Set credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Deploy using BOM
python3 tools/deploy.py functional-release --bom boms/release-2025.10.yaml
```

**What it does:**
- Reads source/target from BOM
- Extracts SPECIFIC entities by reference code (from BOM entity list)
- Compiles flags from profile specified in BOM
- Imports to target with "Replace Existing = Y" and "Add Missing = N"
- Creates deployment archive (bundles + BOM + flags + manifest)
- Pushes archive to Nexus for rollback capability
- Cleans up temporary files

---

### Rollback Deployment
Restore a previous deployment using archived artifacts from Nexus.

**Prerequisites:**
- Previous deployment was successful and archived to Nexus
- BOM has `rollback_artifact` field pointing to Nexus archive

**Example BOM with rollback** (`boms/release-2025.10.yaml`):
```yaml
version: "2.0.0"
change_request: "CR-54321"
profile: functional-cd
source_environment: dev
target_environment: test
description: "Sprint 42 - Incident workflow enhancements"
created_by: "platform-team"

entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"

# Rollback to previous version
rollback_artifact: "nexus://ppm-deployments/2025/CR-54300-v1.9.0-20250930-153000-bundles.zip"
```

**Run rollback:**
```bash
# Set credentials
export PPM_USERNAME=your_username
export PPM_PASSWORD=your_password

# Rollback using BOM
python3 tools/deploy.py rollback --bom boms/release-2025.10.yaml
```

**What it does:**
- Reads `rollback_artifact` from BOM
- Retrieves deployment archive from mock Nexus (`nexus-storage/`)
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

```
boms/
├── baseline/
│   └── {env}-{version}.yaml
└── functional/
    ├── dev/
    ├── test/
    └── prod/
        └── {CR}-{description}-{version}.yaml
```

### **Deployment Workflow**

#### **1. Create BOM** (Feature Branch)
```bash
# Create feature branch
git checkout -b feature/CR-12345-incident-workflow

# Create BOM in appropriate directory
# For dev testing:
cp boms/functional/test/example.yaml boms/functional/dev/CR-12345-incident-v1.0.0.yaml

# Edit BOM with your entities
vim boms/functional/dev/CR-12345-incident-v1.0.0.yaml

# Validate locally
python3 tools/validate_bom.py --file boms/functional/dev/CR-12345-incident-v1.0.0.yaml

# Test locally (optional)
export PPM_USERNAME=testuser
export PPM_PASSWORD=testpass
python3 tools/deploy.py functional-release --bom boms/functional/dev/CR-12345-incident-v1.0.0.yaml
```

#### **2. Create MR** (Dev Deployment)
```bash
# Commit and push
git add boms/functional/dev/CR-12345-incident-v1.0.0.yaml
git commit -m "Add BOM for incident workflow v1.0.0"
git push origin feature/CR-12345-incident-workflow

# Create MR to develop (or main for hotfixes)
# Use "Deployment" MR template
# Request 2 approvals
```

**Pipeline runs:**
- Validate → Deploy (calls `deploy.py functional-release`)

#### **3. Promote to Test** (Copy BOM)
```bash
# After successful dev deployment, promote to test
cp boms/functional/dev/CR-12345-incident-v1.0.0.yaml \
   boms/functional/test/CR-12345-incident-v1.0.0.yaml

# Commit and create MR to develop
git add boms/functional/test/CR-12345-incident-v1.0.0.yaml
git commit -m "Promote incident workflow v1.0.0 to test"
git push

# MR to develop requires 2 approvals
```

**Pipeline runs:**
- Validate → Deploy (calls `deploy.py functional-release`)

#### **4. Promote to Prod** (Copy BOM + Update)
```bash
# After successful test deployment, promote to prod
cp boms/functional/test/CR-12345-incident-v1.0.0.yaml \
   boms/functional/prod/CR-12345-incident-v1.0.0.yaml

# Add rollback artifact from test deployment
vim boms/functional/prod/CR-12345-incident-v1.0.0.yaml
# Set: rollback_artifact: "nexus://ppm-deployments/2025/CR-12345-v1.0.0-...-bundles.zip"

# Commit and create MR to main
git add boms/functional/prod/CR-12345-incident-v1.0.0.yaml
git commit -m "Deploy incident workflow v1.0.0 to prod"
git push

# MR to main requires 3+ approvals
```

**Pipeline runs:**
- Validate → **Manual Review** → Deploy (calls `deploy.py functional-release`)

**Approver reviews:**
1. Check BOM content in MR (entities, reference codes)
2. Verify rollback_artifact is specified
3. Confirm change request is approved
4. Click "Approve" to proceed with deployment

### **Rollback**

```bash
# Create rollback BOM
cat > boms/functional/prod/CR-12345-incident-v0.9.0-rollback.yaml << EOF
version: "0.9.0-rollback"
change_request: "CR-12345-ROLLBACK"
profile: functional-cd
target_environment: prod
description: "Rollback incident workflow to v0.9.0"
created_by: "ops-team"

rollback_artifact: "nexus://ppm-deployments/2025/CR-12300-v0.9.0-...-bundles.zip"
EOF

# Commit and create MR (same approvals as forward deployment)
git add boms/functional/prod/CR-12345-incident-v0.9.0-rollback.yaml
git commit -m "Rollback incident workflow to v0.9.0"
git push

# MR requires 3+ approvals for prod
```

### **Local Validation**

Before creating MR, validate BOM locally:

```bash
# Validate BOM schema
python3 tools/validate_bom.py --file boms/functional/dev/CR-12345-v1.0.0.yaml

# Test deployment with mock scripts
export PPM_USERNAME=testuser
export PPM_PASSWORD=testpass
python3 tools/deploy.py functional-release --bom boms/functional/dev/CR-12345-v1.0.0.yaml
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
