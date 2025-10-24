# PPM Entity Reference

> **Source of Truth:** Entity definitions are maintained in profile configurations.
> Always verify against:
> - [profiles/baseline.yaml](../profiles/baseline.yaml) - Baseline entities
> - [profiles/functional-cd.yaml](../profiles/functional-cd.yaml) - Functional entities
>
> **Official Documentation:** Entity IDs are defined in OpenText PPM documentation:
> - [kMigratorExtract.sh - Entity Type IDs](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122100_InstallAdmin_Server.htm)

---

## Baseline Entities (Infrastructure - 7 entities)

Must exist before functional deployments. Deployed quarterly or on-demand.

**Profile:** [baseline.yaml](../profiles/baseline.yaml)

| Entity | ID | Purpose | Change Freq |
|--------|----|---------| ------------|
| Object Types | 26 | Define object structure | Quarterly |
| Request Header Types | 39 | Define request forms | Quarterly |
| Validations | 13 | Lookup lists and rules | Monthly |
| User Data Contexts | 37 | Shared custom fields | Quarterly |
| Special Commands | 11 | Backend functions | As-needed |
| Environments | 4 | Deployment targets | Rarely |
| Environment Groups | 58 | Target groups | Rarely |

**Philosophy:** Drift correction enabled (add_missing=true)

---

## Functional Entities (Business Logic - 15 entities)

Deploy frequently once baseline is stable. Continuous deployment pattern.

**Profile:** [functional-cd.yaml](../profiles/functional-cd.yaml)

| Entity | ID | Purpose | Change Freq |
|--------|----|---------| ------------|
| Workflows | 9 | Process flows | Weekly |
| Request Types | 19 | Request forms | Weekly |
| Report Types | 17 | Reports | Weekly |
| Overview Page Sections | 61 | Overview page layouts | Weekly |
| Dashboard Modules | 470 | Dashboard pages | Weekly |
| Dashboard Data Sources | 505 | SQL queries behind portlets | Weekly |
| Portlet Definitions | 509 | Dashboard widgets | Weekly |
| Project Types | 521 | Project templates | Monthly |
| Work Plan Templates | 522 | Standard task breakdowns | Monthly |
| Program Types | 901 | Program-level structure | Monthly |
| Portfolio Types | 903 | Portfolio hierarchy | Monthly |
| OData Data Sources | 906 | OData-backed queries | Weekly |
| Custom Menu | 907 | Custom UI menu entries | As-needed |
| Chatbot Intent | 908 | Chatbot intents (PPM 25.2+) | Weekly |
| PPM Integration SDK | 9900 | PPM SDK objects | As-needed |

**Philosophy:** Assumes baseline exists (add_missing=false)

---

## Complete Entity List (All 22 entities, sorted by ID)

| ID | Entity | Category | Description |
|----|--------|----------|-------------|
| 4 | Environment | Baseline | Logical deployment targets referenced in workflows |
| 9 | Workflow | Functional | Process flows for requests/projects |
| 11 | Special Command | Baseline | Reusable backend functions called in workflows |
| 13 | Validation | Baseline | Lookup lists and rules for fields |
| 17 | Report Type | Functional | Parameterized reports |
| 19 | Request Type | Functional | Request forms linked to workflows |
| 26 | Object Type | Baseline | Structure and behavior of objects |
| 37 | User Data Context | Baseline | Shared user data for custom fields |
| 39 | Request Header Type | Baseline | Fields and layout for request forms |
| 58 | Environment Group | Baseline | Logical deployment target groups |
| 61 | Overview Page Section | Functional | Overview page layout definitions |
| 470 | Module (Dashboard) | Functional | Dashboard pages and layouts |
| 505 | Data Source (Dashboard) | Functional | SQL queries behind portlets |
| 509 | Portlet Definition | Functional | Dashboard widgets |
| 521 | Project Type | Functional | Project templates, policies, lifecycle |
| 522 | Workplan Template | Functional | Standard project task breakdowns |
| 901 | Program Type | Functional | Program-level structure |
| 903 | Portfolio Type | Functional | Portfolio containers and hierarchy |
| 906 | OData Data Source | Functional | OData-backed queries (links NOT migrated) |
| 907 | Custom Menu | Functional | Custom UI menu entries |
| 908 | Chatbot Intent | Functional | Chatbot intents (PPM 25.2+) |
| 9900 | PPM Integration SDK | Functional | PPM Integration SDK objects |

---

## Updating This Reference

When modifying entity definitions:

1. **Update the profile YAML first** ([baseline.yaml](../profiles/baseline.yaml) or [functional-cd.yaml](../profiles/functional-cd.yaml))
2. **Update this reference file** to match the profile changes
3. **Verify entity count** matches profile (7 baseline, 15 functional)
4. **Spot-check** descriptions and IDs against profiles

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
