# kMigrator Script Reference

This document provides technical reference for OpenText PPM kMigrator scripts used by the deployment automation system.

**Official Documentation:** [OpenText PPM kMigrator Reference](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm)

---

## kMigratorExtract.sh

The kMigratorExtract script extracts PPM entities from a source environment and creates XML bundle files.

### Required Parameters

| **Parameter** | **Description** |
| --- | --- |
| **username** | PPM service account username |
| **action** | Extraction action: `Search`, `Bundle`, or `Test` |
| **referenceCode** | Unique identifier for the entity (e.g., `WF_INCIDENT_MGMT`) |
| **entityId** | Numeric entity type ID (see Entity ID Reference below) |

### Optional Parameters

| **Parameter** | **Description** |
| --- | --- |
| url | PPM server URL |
| password | PPM service account password |
| delimiter | Field delimiter for output |
| quiet | Runs without verbose output |
| keyword | Search keyword filter |
| primaryKey | Primary key value for lookup |
| primaryKeyName | Primary key field name |
| filename | Output bundle filename |
| uncompressed | Outputs uncompressed XML files |

### Example Usage

```bash
# Extract a workflow by reference code
sh ./kMigratorExtract.sh \
  -username admin \
  -password <password> \
  -url https://ppm.example.com:8443 \
  -action Bundle \
  -referenceCode WF_INCIDENT_MGMT \
  -entityId 9 \
  -filename /tmp/incident_workflow.xml

# Extract all object types (baseline entity)
sh ./kMigratorExtract.sh \
  -username admin \
  -password <password> \
  -url https://ppm.example.com:8443 \
  -action Bundle \
  -entityId 26
```

---

## kMigratorImport.sh

The kMigratorImport script imports PPM entity XML bundles into a target environment.

### Required Parameters

| **Parameter** | **Description** |
| --- | --- |
| **username** | PPM service account username |
| **action** | Import action: `import` (execute) or `trial` (dry-run preview) |
| **filename** | Full path to XML bundle file (must be enclosed in single quotes) |
| **i18n** | Internationalization mode (see below) |
| **refdata** | Reference data handling mode (see below) |
| **flags** | 25-character Y/N string controlling import behavior (see Flags Reference) |

### i18n Parameter Values

| **Value** | **Description** |
| --- | --- |
| `none` | Require exact language and character set match (strict) |
| `charset` | Ignore language and character set warnings (lenient) |
| `locale` | Ignore all warnings (most lenient) |

**Recommendation:** Use `none` for baseline deployments, `charset` for functional deployments.

### refdata Parameter Values

| **Value** | **Description** |
| --- | --- |
| `nochange` | Do not modify reference data tables (recommended) |
| `install` | Install/update reference data from bundle (use with caution) |

**Recommendation:** Use `nochange` unless explicitly installing reference data updates.

### Optional Parameters

| **Parameter** | **Description** |
| --- | --- |
| url | PPM server URL |
| password | PPM service account password |
| report | Generate detailed import report |
| ignorePpmVersionDifference | Continue import despite PPM version mismatch (use with caution) |

### Example Usage

```bash
# Import a workflow bundle (functional deployment)
sh ./kMigratorImport.sh \
  -username admin \
  -password <password> \
  -url https://ppm.example.com:8443 \
  -action import \
  -filename '/tmp/incident_workflow.xml' \
  -i18n charset \
  -refdata nochange \
  -flags NYNNNYYYYNNNYNYYYYYYYYYYN

# Trial run (preview) for baseline deployment
sh ./kMigratorImport.sh \
  -username admin \
  -password <password> \
  -url https://ppm.example.com:8443 \
  -action trial \
  -filename '/tmp/baseline_entities.xml' \
  -i18n none \
  -refdata nochange \
  -flags YYYYYNNNNYYYNYYYYNNNNNNN
```

**Important:**
- Full file path must be enclosed in single quotes
- Flags parameter must be exactly 25 characters (Y or N)
- Use `action=trial` to preview changes before executing

---

## Import Flags Reference

The 25-character flags string controls kMigratorImport behavior. Each position corresponds to a specific entity type or import option.

**Format:** `YNYNNYYYYNNNYNYYYYYYYYYYN` (25 characters, Y or N only)

### Flag Positions and Meanings

| **Flag #** | **Description** |
| --- | --- |
| Flag 1 | Replace existing Object Type |
| Flag 2 | Replace existing Request Type |
| Flag 3 | Replace existing Request Header Type |
| Flag 4 | Replace existing Special Command |
| Flag 5 | Replace existing Validation |
| Flag 6 | Replace existing Workflow |
| Flag 7 | Replace existing Report Type |
| Flag 8 | Replace existing Workplan Template |
| Flag 9 | Replace existing Workflow Step Sources |
| Flag 10 | Add missing Environment |
| Flag 11 | Add missing Security Group |
| Flag 12 | Add missing Request Status |
| Flag 13 | Replace existing Overview Page Section |
| Flag 14 | Replace existing User Data Context |
| Flag 15 | Replace existing Portlet Definition |
| Flag 16 | Replace existing Module |
| Flag 17 | Replace existing Data Source |
| Flag 18 | Replace existing Project Type |
| Flag 19 | Replace existing Sub workflow |
| Flag 20 | Replace existing Program Type |
| Flag 21 | Replace existing OData Data Source |
| Flag 22 | Replace existing Portfolio Type |
| Flag 23 | Replace existing PPM Integration SDK |
| Flag 24 | Replace existing menu |
| Flag 25 | Replace existing Chatbot intents (25.2+) |

See `profiles/baseline.yaml` and `profiles/functional-cd.yaml` for actual flag values used by this system.

### Flag Usage Notes

**Flag 16 (Module):**
- If replacing Portfolio Type (Flag 22 = Y), you must also set Flag 16 = Y

**Flag 24 (Custom Menu):**
- This flag is ignored - existing menu is always replaced regardless of Y/N value

**Flag 7 (Report Type):**
- If replacing Chatbot Intents (Flag 25 = Y), you must also set Flag 7 = Y

### Standard Flag Profiles

Our deployment system uses two standard flag profiles:

**Baseline Profile** (`baseline`):
```
YYYYYNNNNYYYYYNNNNNNNNN
```
- Deploys: Object Types, Request Header Types, Validations, User Data Contexts, Special Commands, Environments, Environment Groups
- Adds missing: Environments, Security Groups, Request Statuses
- Does NOT deploy: Workflows, Report Types, Portlets, Dashboard Modules, Dashboard Data Sources, Work Plan Templates, Project Types, Program Types, Portfolio Types, OData Data Sources, Custom Menus, Chatbot Intents, PPM Integration SDK

**Functional-CD Profile** (`functional-cd`):
```
NYNNNYYYYNNNYNYYYYYYYYYN
```
- Deploys: Workflows, Request Types, Report Types, Portlet Definitions, Dashboard Modules, Dashboard Data Sources, Overview Page Sections, Work Plan Templates, Project Types, Program Types, Portfolio Types, OData Data Sources, Custom Menu, Chatbot Intent, PPM Integration SDK
- Does NOT add missing: Environments, Security Groups, Request Statuses (baseline must already exist)
- Does NOT deploy: Object Types, Request Header Types, Special Commands, Validations, User Data Contexts, Environment Groups

**Note:** Chatbot Intent (entity 908) is in the deployment list but `replace_chatbot_intents` flag is set to `false`. Verify entity list vs flags in `profiles/functional-cd.yaml`.

See `profiles/baseline.yaml` and `profiles/functional-cd.yaml` for complete flag configuration.

---

## Entity ID Reference

Entity IDs are used by kMigratorExtract to identify which entity type to extract.

| **Entity ID** | **Entity Type** | **Category** | **Description** |
| --- | --- | --- | --- |
| 4 | Environment | Baseline | Logical deployment targets referenced in workflows |
| 9 | Workflow | Functional | Process flows for requests/projects |
| 11 | Special Command | Baseline | Reusable backend functions called in workflows |
| 13 | Validation | Baseline | Lookup lists and rules for fields |
| 17 | Report Type | Functional | Parameterized reports |
| 19 | Request Type | Functional | Request forms linked to workflows |
| 26 | Object Type | Baseline | Structure and behavior of objects (requests, projects, packages) |
| 37 | User Data Context | Baseline | Shared user data for custom fields |
| 39 | Request Header Type | Baseline | Fields and layout for request forms |
| 58 | Environment Group | Baseline | Logical deployment target groups |
| 61 | Overview Page Section | Functional | Overview page layout definitions |
| 470 | Module | Functional | Dashboard pages and layouts |
| 505 | Data Source | Functional | SQL queries behind portlets |
| 509 | Portlet Definition | Functional | Dashboard widgets |
| 521 | Project Type | Functional | Project templates, policies, lifecycle |
| 522 | Workplan Template | Functional | Standard project task breakdowns |
| 901 | Program Type | Functional | Program-level structure |
| 903 | Portfolio Type | Functional | Portfolio containers and hierarchy |
| 906 | OData Data Source | Functional | OData-backed queries (links NOT migrated) |
| 907 | Custom Menu | Functional | Custom UI menu entries |
| 908 | Chatbot Intent | Functional | Chatbot intents (PPM 25.2+) |
| 9900 | PPM Integration SDK | Functional | PPM Integration SDK objects |

### Entity Categories

**Baseline Entities:**
- Must be version-controlled and aligned across all environments
- Deployed once per alignment cycle
- Changing them mid-flight can break workflows and requests
- Examples: Object Types, Request Header Types, Validations, Commands

**Functional Entities:**
- Frequently changed business logic
- Deployed continuously once baseline is stable
- Safe to replace at any time with proper testing
- Examples: Workflows, Request Types, Reports, Dashboards

### Special Notes

**Request Statuses:**
- Part of Request Header Types (Entity ID 39)
- No separate entity ID
- Controlled by Flag 12 (Add missing Request Status)

**Security Groups:**
- Referenced but not migrated automatically
- Must exist in all environments before workflow deployment
- Controlled by Flag 11 (Add missing Security Group)

**OData Data Sources (906):**
- OData links defined for data sources are NOT migrated
- Only the data source definition itself is migrated

---

## Flag Compilation System

The deployment automation compiles flags from YAML profiles instead of hardcoding 25-character strings.

### Profile Structure

```yaml
# config/profiles/functional-cd.yaml
entities:
  object_types: no          # Flag 1
  request_types: yes        # Flag 2
  request_header_types: no  # Flag 3
  special_commands: no      # Flag 4
  validations: no           # Flag 5
  workflows: yes            # Flag 6
  report_types: yes         # Flag 7
  # ... 18 more flags
```

### Flag Compiler

The flag compiler (`tools/config/flags.py`) converts YAML profiles to 25-character strings:

```bash
# Compile baseline profile
python3 -m tools.config.flags baseline
# Output: YNYYYNNNNYYYNYYYYNNNNNNN

# Compile functional-cd profile
python3 -m tools.config.flags functional-cd
# Output: NYNNNYYYYNNNYNYYYYYYYYYYN
```

**Benefits:**
- Human-readable flag configuration
- Version-controlled in Git
- Self-documenting (each flag has descriptive name)
- Prevents typos in 25-character strings

---

## Common Import Scenarios

### Scenario 1: Bootstrap New Environment

First-time deployment to empty environment:

```bash
# Step 1: Deploy baseline with "add missing" enabled
python3 -m tools.deployment.orchestrator deploy \
  --type baseline \
  --bom boms/baseline.yaml

# Flags used: YNYYYNNNNYYYNYYYYNNNNNNN
# - Replaces all baseline entities
# - Adds missing environments, security groups, statuses

# Step 2: Deploy functional entities
python3 -m tools.deployment.orchestrator deploy \
  --type functional \
  --bom boms/functional.yaml

# Flags used: NYNNNYYYYNNNYNYYYYYYYYYYN
# - Replaces functional entities only
# - Does NOT add missing baseline items (already exist)
```

### Scenario 2: Continuous Deployment (Aligned Environments)

Environments already aligned, deploying workflow changes:

```bash
# Only deploy functional changes
python3 -m tools.deployment.orchestrator deploy \
  --type functional \
  --bom boms/functional.yaml

# Flags used: NYNNNYYYYNNNYNYYYYYYYYYYN
# - Replaces workflows, request types, reports, dashboards
# - Does NOT touch baseline entities
# - Does NOT add missing items (enforces baseline alignment)
```

### Scenario 3: Baseline Realignment

Quarterly baseline synchronization:

```bash
# Redeploy baseline entities
python3 -m tools.deployment.orchestrator deploy \
  --type baseline \
  --bom boms/baseline.yaml

# Flags used: YNYYYNNNNNNNNYYYYNNNNNNN
# - Replaces all baseline entities
# - Does NOT add missing items (detects drift instead)
# - Missing environments/statuses = signal of upstream drift
```

---

## Troubleshooting

### Error: "Import failed - missing environment"

**Cause:** Functional deployment tried to use environment that doesn't exist in target

**Solution:**
1. Check baseline alignment between source and target
2. Deploy baseline entities first with Flag 10 = Y (add missing environments)
3. Then deploy functional entities

### Error: "Import failed - missing security group"

**Cause:** Workflow references security group that doesn't exist in target

**Solution:**
1. Manually create security group in target environment
2. Or deploy baseline with Flag 11 = Y (add missing security groups)
3. Verify security groups exist before functional deployment

### Error: "Import failed - reference data mismatch"

**Cause:** Source and target have different reference data versions

**Solution:**
1. Check if `refdata=install` is appropriate for this deployment
2. Verify PPM versions match between source and target
3. Consider using `ignorePpmVersionDifference` if data model unchanged

### Trial Mode Returns Errors

**Use Case:** Preview import before executing

```bash
# Run trial (dry-run) to check for issues
sh ./kMigratorImport.sh \
  -action trial \
  -filename '/tmp/bundle.xml' \
  -i18n charset \
  -refdata nochange \
  -flags NYNNNYYYYNNNYNYYYYYYYYYYN

# Review output for errors before running with -action import
```

---

## References

- **Official kMigrator Documentation:** [OpenText PPM kMigrator Reference](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm)
- **Deployment Profiles:** `config/profiles/*.yaml`
- **Flag Compiler:** `tools/config/flags.py`
- **Entity Migration Guide:** `entity_migration.md`
- **Key Concepts:** `KEY_CONCEPTS.md`
