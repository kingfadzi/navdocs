# Key Concepts: PPM Deployment System

## Overview

Declarative, opinionated deployment system for OpenText PPM entity migration with:
- **BOM-driven deployments** - All deployments defined in version-controlled YAML files
- **Baseline-first approach** - Stable foundation before continuous deployment
- **GitLab CI/CD pipeline** - Automated deployments with approval gates
- **Nexus rollback** - Every deployment archived for instant rollback
- **Mock-first testing** - Test locally without real PPM server

---

## Core Components

### 1. **Bill of Materials (BOM)**
YAML manifest that defines:
- What entities to deploy (reference codes)
- Source and target environments
- Version number (semantic versioning)
- Change request number (for functional)
- Rollback artifact (for prod)

**Example:**
```yaml
version: "1.0.0"
change_request: "CR-12345"
profile: functional-cd
source_environment: dev
target_environment: test
entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
rollback_artifact: "nexus://ppm-deployments/2025/CR-12300-v0.9.0-bundles.zip"
```

### 2. **Profiles**
Define deployment behavior via structured flags:
- **baseline.yaml** - Replace existing = Y, Add missing = Y (for infrastructure)
- **functional-cd.yaml** - Replace existing = Y, Add missing = N (for business logic)

Profiles compile to 25-character Y/N flag string automatically.

### 3. **Deployment Script (`deploy.py`)**
Single orchestrator that:
1. Extracts entities from source
2. Imports to target with compiled flags
3. Archives deployment to Nexus
4. Cleans up temporary files

Used for both local testing and CI/CD.

### 4. **GitLab Pipeline**
Three stages:
- **Validate** - BOM schema checks
- **Review** - Manual approval (prod only)
- **Deploy** - Calls `deploy.py` automatically

### 5. **Nexus Mock**
Local file-based mock that simulates artifact repository:
- Stores deployment archives (bundles + BOM + flags)
- Enables rollback without re-extracting
- No external dependencies for testing

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
| Portlet Definitions | 509 | LOW | Weekly |
| Dashboard Modules | 470 | LOW | Weekly |
| Work Plan Templates | 522 | LOW | Monthly |
| Project Types | 521 | MEDIUM | Monthly |

**Philosophy:** Drift is tolerated (Add Missing = N, baseline handles dependencies)

---

## Deployment Strategy

### **Baseline Repave**
Deploy ALL baseline entity types (full sync).

* **When:** Initial setup, quarterly alignment, or on-demand
* **Scope:** All 7 baseline entity types
* **Flags:** Replace = Y, Add Missing = Y
* **Risk:** HIGH - affects all downstream entities
* **Approval:** 2 (non-prod), 3+ (prod) with platform team

**BOM Example:**
```yaml
version: "1.0.0"
profile: baseline
source_environment: prod
target_environment: test
description: "Q4 2025 baseline alignment"
created_by: "ops-team"
```

### **Functional Release**
Deploy SPECIFIC functional entities (selective).

* **When:** Sprint releases, feature deployments
* **Scope:** Only entities in BOM
* **Flags:** Replace = Y, Add Missing = N
* **Risk:** MEDIUM - isolated to specific entities
* **Approval:** 2 (non-prod), 3+ (prod)

**BOM Example:**
```yaml
version: "2.0.0"
change_request: "CR-54321"
profile: functional-cd
source_environment: dev
target_environment: test
entities:
  - entity_id: 9
    reference_code: "WF_INCIDENT_MGMT"
    entity_type: "Workflow"
rollback_artifact: "nexus://ppm-deployments/2025/CR-54300-v1.9.0-bundles.zip"
```

---

## Branching & Promotion Flow

### **Branch Strategy**

| Branch | Deploys To | MR Approvals | Pipeline Gate |
|--------|------------|--------------|---------------|
| `feature/*` | Dev | 2 | None |
| `develop` | Test | 2 | None |
| `main` | Prod | 3+ | Manual review |

### **Promotion Workflow**

```
1. Feature branch → boms/functional/dev/CR-12345-v1.0.0.yaml
   └─> MR (2 approvals) → Merge → Auto-deploy to dev

2. Copy to test → boms/functional/test/CR-12345-v1.0.0.yaml
   └─> MR to develop (2 approvals) → Merge → Auto-deploy to test

3. Copy to prod → boms/functional/prod/CR-12345-v1.0.0.yaml
   └─> Add rollback_artifact
   └─> MR to main (3+ approvals) → Manual review → Deploy to prod
```

Each environment gets its own BOM for clear audit trail.

---

## Rollback Strategy

### **Archive on Success**
Every successful deployment creates:
```
CR-12345-v1.0.0-20251007-bundles.zip
├── bundles/              # Extracted XML files
├── bom.yaml              # Original BOM
├── flags.txt             # Exact flags used
└── manifest.yaml         # Metadata (version, timestamp, checksums)
```

Pushed to Nexus: `nexus://ppm-deployments/2025/CR-12345-v1.0.0-bundles.zip`

### **Rollback Execution**

1. Create rollback BOM pointing to Nexus artifact
2. Get same approvals as forward deployment
3. Pipeline downloads archive and redeploys using **original flags**

**Key:** Rollback uses exact flags from original deployment for consistency.

---

## Governance & Approvals

### **Approval Matrix**

| Deployment | Environment | MR Approvals | Pipeline Gate | Total |
|------------|-------------|--------------|---------------|-------|
| Functional | Dev | 2 | None | 2 |
| Functional | Test | 2 | None | 2 |
| Functional | Prod | 3+ | Manual | 4+ |
| Baseline | Dev | 2 | None | 2 |
| Baseline | Test | 2 (+ platform) | None | 2 |
| Baseline | Prod | 3+ (+ platform) | Manual | 4+ |

### **CODEOWNERS**
- Baseline BOMs → `@platform-team` required
- Prod BOMs → `@tech-leads` + `@ops-team` required
- Profiles/schemas → `@platform-team` required

---

## Key Design Principles

* **Opinionated** - Two deployment types (baseline/functional), no overrides
* **Declarative** - BOMs are version-controlled, reviewed via MR
* **Idempotent** - Same BOM = same result (safe to rerun)
* **Testable** - Mock scripts work without real PPM
* **Lean** - Reuses `deploy.py` for local and CI/CD
* **Traceable** - Git commits + Nexus archives = full audit trail

---

## Benefits

### **For Platform Engineers:**
- No manual flag strings (compiled from profiles)
- No manual kMigrator commands (automated by deploy.py)
- Instant rollback (download from Nexus, redeploy)

### **For Operations:**
- Clear approval gates (2 or 3+ depending on environment)
- BOM review before deployment (see exactly what will change)
- Audit trail (Git history + Nexus artifacts)

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
1. Create BOM in feature branch
2. Test in dev → promote to test → promote to prod
3. Each step requires MR approval

### **Quarterly Baseline Sync**
1. Platform team creates baseline BOM
2. Test in dev/test first
3. Schedule prod deployment (off-hours)
4. Requires 3+ approvals including platform team

### **Emergency Rollback**
1. Create rollback BOM pointing to previous Nexus artifact
2. Get expedited approvals (same as forward: 3+ for prod)
3. Deploy (fast: no extraction needed)

---

## References

- [OpenText PPM kMigrator Documentation](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm)
- [Semantic Versioning](https://semver.org/)
- [GitLab CI/CD](https://docs.gitlab.com/ee/ci/)
