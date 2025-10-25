# PPM Entity Reference

> **Source of Truth:** Entity deployment lists are defined in BOM files, validated by schemas.
>
> **Architecture:**
> - **BOMs** ([boms/](boms/)) - Define WHAT entities to deploy
> - **Profiles** ([profiles/](profiles/)) - Define HOW to deploy (flags only)
> - **Schemas** ([schemas/](schemas/)) - Validate entity types allowed per category
>
> **References:**
> - [schemas/entity-types.yaml](schemas/entity-types.yaml) - Internal entity type reference
> - [OpenText PPM Documentation - Entity Type IDs](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122100_InstallAdmin_Server.htm)

---

## Understanding Baseline vs Functional Entities

### Baseline (Infrastructure) Entity Types - 7 Available Types

**Purpose:** Data structure, field definitions, and core infrastructure that must exist BEFORE any functional entities can be imported.

**Characteristics:**
- Foundational configuration
- Defines what objects ARE at the data/structure level
- Must be version-controlled and aligned across all environments
- Deployed quarterly or on-demand for infrastructure alignment

**Examples:**
- Object Types (26) - Define what a "project" or "request" IS at the data level
- Validations (13) - Lookup lists and field rules
- Environments (4) - Deployment targets (referenced by functional entities)

**Philosophy:** Drift correction enabled (add_missing=true) - baseline alignment expected

---

### Functional (Business Logic) Entity Types - 15 Available Types

**Purpose:** Business processes, workflows, reporting, and customizations that operate ON TOP OF the baseline infrastructure.

**Characteristics:**
- Business logic and processes
- Defines HOW business operations work
- Depends on baseline entities existing first
- Deployed continuously (weekly/monthly)

**Examples:**
- Request Types (19) - Define HOW requests are processed
- Workflows (9) - Business process flows and automation
- Reports (17) - Business intelligence and reporting

**Philosophy:** Assumes baseline exists (add_missing=false) - strict dependency enforcement

---

### Critical Dependency

**Deployment order matters:**
1. **First:** Deploy baseline entities to establish infrastructure
2. **Then:** Deploy functional entities that reference the baseline

**Example dependency chain:**
- Workflows (functional) -> reference Environments (baseline)
- Request Types (functional) -> reference Validations (baseline)
- Reports (functional) -> reference Object Types (baseline)

Attempting to deploy functional entities before baseline will result in import failures due to missing dependencies.

---

## Baseline Entity Types (Infrastructure - 7 types available)

Must exist before functional deployments. Deployed quarterly or on-demand.

**Profile:** [baseline.yaml](profiles/baseline.yaml)

| Entity | ID | Description | Change Freq |
|--------|----|---------| ------------|
| Environment Groups | 58 | Logical deployment target groups | Rarely |
| Environments | 4 | Logical deployment targets referenced in workflows | Rarely |
| Object Types | 26 | Structure and behavior of objects | Quarterly |
| Request Header Types | 39 | Fields and layout for request forms | Quarterly |
| Special Commands | 11 | Reusable backend functions called in workflows | As-needed |
| User Data Contexts | 37 | Shared user data for custom fields | Quarterly |
| Validations | 13 | Lookup lists and rules for fields | Monthly |

**Flag String:** `YNYYYNNNNYYYNYNNNNNNNNNNNN`

**Flags Enabled:**
- Replace baseline entities (Flags 1, 3-5, 14)
- **Add missing Environment** (Flag 10 = Y) - Creates missing Environments during import
- **Add missing Security Group** (Flag 11 = Y) - Creates empty security groups if referenced
- **Add missing Request Status** (Flag 12 = Y) - Creates missing request statuses

**Philosophy:** Drift correction enabled - expects and handles differences between environments

**Does NOT Extract/Deploy:** Functional entities (Workflows, Reports, Dashboards, etc.)

---

## Functional Entity Types (Business Logic - 15 types available)

Deploy frequently once baseline is stable. Continuous deployment pattern.

**Profile:** [functional-cd.yaml](profiles/functional-cd.yaml)

| Entity | ID | Description | Change Freq |
|--------|----|---------| ------------|
| Chatbot Intent | 908 | Chatbot intents (PPM 25.2+) | Weekly |
| Custom Menu | 907 | Custom UI menu entries | As-needed |
| Dashboard Data Sources | 505 | SQL queries behind portlets | Weekly |
| Dashboard Modules | 470 | Dashboard pages and layouts | Weekly |
| OData Data Sources | 906 | OData-backed queries (links NOT migrated) | Weekly |
| Overview Page Sections | 61 | Overview page layout definitions | Weekly |
| Portlet Definitions | 509 | Dashboard widgets | Weekly |
| Portfolio Types | 903 | Portfolio containers and hierarchy | Monthly |
| PPM Integration SDK | 9900 | PPM Integration SDK objects | As-needed |
| Program Types | 901 | Program-level structure | Monthly |
| Project Types | 521 | Project templates, policies, lifecycle | Monthly |
| Report Types | 17 | Parameterized reports | Weekly |
| Request Types | 19 | Request forms linked to workflows | Weekly |
| Workflows | 9 | Process flows for requests/projects | Weekly |
| Work Plan Templates | 522 | Standard project task breakdowns | Monthly |

**Flag String:** `NYNNNYYYYNNNYNYYYYYYYYYYY`

**Flags Enabled:**
- Replace functional entities (Flags 2, 6-9, 13, 15-25)
- **Add missing operations DISABLED** (Flags 10-12 = N) - Strict dependency enforcement

**Philosophy:** Assumes baseline exists - fails if dependencies missing (enforces proper deployment order)

**Does NOT Extract/Deploy:** Baseline entities (Object Types, Validations, Environments, etc.)

---

## Updating This Reference

When adding new entity types to the system:

1. **Update schemas** ([schemas/bom-baseline-schema.json](schemas/bom-baseline-schema.json) or [schemas/bom-functional-schema.json](schemas/bom-functional-schema.json)) to allow new entity IDs
2. **Update schemas/entity-types.yaml** with new entity type documentation
3. **Update this reference file** to include new entity type descriptions
4. **Update profile flags** if new replacement flags are needed for the entity type
5. **Verify entity type count** (7 baseline types, 15 functional types)

---

## Entity Categories Explained

**Baseline Entities:**
- Must be version-controlled and aligned across all environments
- Deployed once per alignment cycle (quarterly or on-demand)
- Contain field definitions, validations, and core structure
- Changing them mid-flight can break workflows and requests
- Drift correction enabled (add_missing=true)

**Functional Entities:**
- Frequently changed business logic
- Deployed continuously once baseline is stable
- Safe to replace at any time with proper testing
- Assumes baseline infrastructure already exists
- Drift correction disabled (add_missing=false)

---

## Deployment Order

**Critical:** Baseline must be deployed BEFORE functional entities.

1. **First - Baseline Deployment:**
   ```bash
   python3 -m tools.deployment.orchestrator deploy --type baseline --bom boms/baseline.yaml
   ```
   - Deploys specific infrastructure entities listed in BOM
   - Adds missing environments, security groups, statuses
   - Creates foundation for functional entities

2. **Then - Functional Deployment:**
   ```bash
   python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
   ```
   - Deploys specific business logic entities listed in BOM
   - References baseline entities
   - Fails if baseline not present (intentional safety check)
