# PPM Deployment System

Git-driven deployment pipeline for OpenText PPM. Edit BOM files, commit, deploy automatically.

---

## How It Works

1. Edit `boms/baseline.yaml` or `boms/functional.yaml`
2. Commit and push
3. Pipeline validates and deploys automatically

**Two deployment types:**
- **Baseline** - SPECIFIC foundational entities listed in BOM (Object Types, Request Header Types, Validations, User Data Contexts, Special Commands, Environments, Environment Groups)
- **Functional** - SPECIFIC business logic entities listed in BOM (Workflows, Request Types, Reports, Overview Pages, Dashboards, Portlets, Work Plans, Project/Program/Portfolio Types, OData Sources, Custom Menus, Chatbot Intents, PPM SDK)

---

## Quick Start

### Edit a BOM File

**Baseline** (`boms/baseline.yaml`):
```yaml
version: "1.0"
category: baseline
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
entities:
  - id: 26
    reference_code: "OBJ_CUSTOM_ASSET"
    name: "Custom Asset Object Type"
  - id: 13
    reference_code: "VAL_PRIORITY_LEVELS"
    name: "Priority Levels Validation"
```

**Functional** (`boms/functional.yaml`):
```yaml
version: "2.0"
category: functional
profile: functional-cd
source_server: dev-ppm-useast
target_server: test-ppm-useast
change_request: "CR-12345"
entities:
  - id: 9
    reference_code: "WF_INCIDENT_MGMT"
    name: "Incident Management Workflow"
  - id: 19
    reference_code: "REQ_TYPE_INCIDENT"
    name: "Incident Request Type"
```

### Deploy

**Via Pipeline** (automatic):
```bash
git add boms/functional.yaml
git commit -m "Deploy incident workflow"
git push
```

**Via CLI** (manual):
See [MANUAL_DEPLOYMENT_GUIDE.md](MANUAL_DEPLOYMENT_GUIDE.md)

---

## Repository Structure

- **boms/** - Bill of Materials (WHAT to deploy)
  - `baseline.yaml` - Baseline deployment BOM
  - `functional.yaml` - Functional deployment BOM
- **config/** - Configuration files
  - `deployment-config.yaml` - Server/storage config
  - `rules.yaml` - Governance rules
- **profiles/** - Deployment profiles (HOW to deploy)
  - `baseline.yaml` - Baseline flags configuration
  - `functional-cd.yaml` - Functional flags configuration
- **schemas/** - BOM validation schemas
  - `bom-baseline-schema.json` - Baseline BOM validation schema
  - `bom-functional-schema.json` - Functional BOM validation schema
  - `entity-types.yaml` - Entity type reference
  - `README.md` - Schema documentation
- **tools/** - Python deployment system
- **templates/** - CI/CD pipeline templates
- `.gitlab-ci.yml` - Main pipeline configuration

---

## Pipeline Behavior

| Files Changed | Pipeline Action |
|---------------|----------------|
| `baseline.yaml` only | Baseline deployment |
| `functional.yaml` only | Functional deployment |
| Both files | Baseline first, then functional |

**Stages:**
1. **Validate** - JSON schema validation + governance rules
2. **Extract** - Pull entities from source server
3. **Import** - Push entities to target server
4. **Archive** - Create rollback package

---

## Documentation

**For manual deployments:**
- [MANUAL_DEPLOYMENT_GUIDE.md](MANUAL_DEPLOYMENT_GUIDE.md) - CLI commands, local/remote deployments

**For deep dive:**
- [KEY_CONCEPTS.md](KEY_CONCEPTS.md) - Architecture, storage, executors, secrets
- [ENTITY_REFERENCE.md](ENTITY_REFERENCE.md) - Entity types, profiles, flag configurations
- [PIPELINE_ARCHITECTURE.md](PIPELINE_ARCHITECTURE.md) - Pipeline execution flow and stages
- [KMIGRATOR_REFERENCE.md](KMIGRATOR_REFERENCE.md) - kMigrator flags and parameters

---

## Local Testing

Test BOMs locally before committing:

```bash
# Setup
export DEPLOYMENT_ENV=local
export PPM_ADMIN_USER=testuser
export PPM_ADMIN_PASSWORD=testpass

# Validate and deploy
python3 -m tools.deployment.orchestrator validate --bom boms/functional.yaml
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

See [MANUAL_DEPLOYMENT_GUIDE.md](MANUAL_DEPLOYMENT_GUIDE.md) for complete CLI reference.

---

## Rollback

Set `rollback_pipeline_id` in BOM, then deploy:

```yaml
rollback_pipeline_id: 12345  # Previous successful pipeline
```

```bash
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
```

---

## Governance Rules

Defined in `config/rules.yaml`:
- Promotion order (dev -> test -> staging -> prod)
- Production requires rollback plan
- Production requires change request
- No deploying from prod to dev

Validation happens automatically in pipeline and CLI.
