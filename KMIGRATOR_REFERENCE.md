# kMigrator Script Reference

This document provides technical reference for OpenText PPM kMigrator scripts used by the deployment automation system.

**Official Documentation:** [OpenText PPM kMigrator Reference](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm)

---

## kMigratorExtract.sh

The kMigratorExtract script extracts PPM entities from a source environment and creates XML bundle files.

**Official Documentation:** [kMigratorExtract.sh - OpenText PPM 25.1-25.3](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122100_InstallAdmin_Server.htm)

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

# Extract specific object type (baseline entity)
sh ./kMigratorExtract.sh \
  -username admin \
  -password <password> \
  -url https://ppm.example.com:8443 \
  -action Bundle \
  -referenceCode OBJ_CUSTOM_ASSET \
  -entityId 26 \
  -filename /tmp/object_type.xml
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
| `nochange` | Do not modify reference data tables |
| `install` | Install/update reference data from bundle |

**Our system uses:**
- **Baseline deployments:** `refdata=install` (syncs reference data tables)
- **Functional deployments:** `refdata=nochange` (business logic only, no system changes)

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
  -refdata install \
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

Our deployment system uses two standard flag profiles defined in `profiles/`:

**For complete profile details, entity lists, and flag configurations, see:**
- [Baseline Entities](ENTITY_REFERENCE.md#baseline-entities-infrastructure---7-entities) - Flag string: `YNYYYNNNNYYYNYNNNNNNNNNNNN`
- [Functional Entities](ENTITY_REFERENCE.md#functional-entities-business-logic---15-entities) - Flag string: `NYNNNYYYYNNNYNYYYYYYYYYYY`

**Quick reference:**
- **Baseline:** Deploys 7 infrastructure entities (Object Types, Validations, Environments, etc.)
  - Flag string: `YNYYYNNNNYYYNYNNNNNNNNNNNN`
  - Add missing operations enabled (drift correction)
  - Import: `i18n=none`, `refdata=install` (syncs reference data)

- **Functional-CD:** Deploys 15 business logic entities (Workflows, Reports, Dashboards, etc.)
  - Flag string: `NYNNNYYYYNNNYNYYYYYYYYYYY`
  - Add missing operations disabled (strict dependencies)
  - Import: `i18n=charset`, `refdata=nochange` (business logic only)

See `profiles/baseline.yaml` and `profiles/functional-cd.yaml` for source configuration.

---

## Entity ID Reference

Entity IDs are used by kMigratorExtract to identify which entity type to extract.

**Official Documentation:** [Entity Type IDs - OpenText PPM](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122100_InstallAdmin_Server.htm)

**Entity lists:**
- [Baseline entities (7)](ENTITY_REFERENCE.md#baseline-entities-infrastructure---7-entities) - IDs 4, 11, 13, 26, 37, 39, 58
- [Functional entities (15)](ENTITY_REFERENCE.md#functional-entities-business-logic---15-entities) - IDs 9, 17, 19, 61, 470, 505, 509, 521, 522, 901, 903, 906, 907, 908, 9900

For detailed descriptions, deployment frequency, and categorization, see the [Entity Reference](ENTITY_REFERENCE.md).

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

**Environment Groups (Entity 58):**
- Category: Baseline (infrastructure) entity
- Can be extracted using entity ID 58
- Imported if explicitly included in migration bundle
- **Important:** Flag 10 (Add missing Environment) applies to Environments (4) only, NOT Environment Groups (58)
- If Environment Groups are only referenced but not bundled, migration may partially create headers/metadata (unreliable behavior)
- **Best practice:** Always extract and bundle both Environments (4) AND Environment Groups (58) together in baseline deployments
- Functional entities (Request Types, Workflows, etc.) may reference Environment Groups - ensure baseline is deployed first to avoid dependency failures

**OData Data Sources (906):**
- OData links defined for data sources are NOT migrated
- Only the data source definition itself is migrated

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
# Import: i18n=none, refdata=install
# - Replaces all baseline entities
# - Adds missing environments, security groups, statuses
# - Updates reference data tables

# Step 2: Deploy functional entities
python3 -m tools.deployment.orchestrator deploy \
  --type functional \
  --bom boms/functional.yaml

# Flags used: NYNNNYYYYNNNYNYYYYYYYYYYN
# Import: i18n=charset, refdata=nochange
# - Replaces functional entities only
# - Does NOT add missing baseline items (already exist)
# - Does NOT modify reference data (business logic only)
```

### Scenario 2: Continuous Deployment (Aligned Environments)

Environments already aligned, deploying workflow changes:

```bash
# Only deploy functional changes
python3 -m tools.deployment.orchestrator deploy \
  --type functional \
  --bom boms/functional.yaml

# Flags used: NYNNNYYYYNNNYNYYYYYYYYYYN
# Import: i18n=charset, refdata=nochange
# - Replaces workflows, request types, reports, dashboards
# - Does NOT touch baseline entities
# - Does NOT add missing items (enforces baseline alignment)
# - Does NOT modify reference data
```

### Scenario 3: Baseline Realignment

Quarterly baseline synchronization:

```bash
# Redeploy baseline entities
python3 -m tools.deployment.orchestrator deploy \
  --type baseline \
  --bom boms/baseline.yaml

# Flags used: YNYYYNNNNNNNNYYYYNNNNNNN
# Import: i18n=none, refdata=install
# - Replaces all baseline entities
# - Does NOT add missing items (detects drift instead)
# - Updates reference data tables
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
- **Deployment Profiles:** `profiles/*.yaml` - See [baseline.yaml](profiles/baseline.yaml) and [functional-cd.yaml](profiles/functional-cd.yaml)
- **Flag Compilation System:** [KEY_CONCEPTS.md - Profiles and Flag Compilation](KEY_CONCEPTS.md#profiles-and-flag-compilation)
- **Entity Reference:** [ENTITY_REFERENCE.md](ENTITY_REFERENCE.md)
