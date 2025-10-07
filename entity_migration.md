# Migratable Entities Categorized by Role

| **Category** | **Entity** | **Entity ID** | **What It Does** | **Why It Matters for Baseline & CD** |
| --- | --- | --- | --- | --- |
| **Baseline (Plumbing)** | **Object Types** | **26** | Define structure and behavior of objects (requests, projects, packages) | Must match everywhere or request types/projects won't work correctly |
|  | **Request Header Types** | **39** | Define fields and layout for request forms | Baseline must be aligned so request types behave the same in every environment |
|  | **Request Statuses***(part of header types)* | **-** | Define lifecycle states (Submitted, Approved, Closed) | Missing statuses block migrations; baseline them once |
|  | **Validations** | **13** | Define lookup lists and rules for fields | Inconsistent validations cause requests to behave differently |
|  | **User Data Contexts** | **37** | Define shared user data for custom fields | Keep aligned so environment-specific data is consistent |
|  | **Special Commands** | **11** | Reusable backend functions called in workflows | Missing commands break workflow steps |
|  | **Environments**  | **4**  | Logical deployment targets referenced in workflows | Missing environments cause package promotion failures |
|  | **Environment Groups** | **58** | Logical deployment targets referenced in workflows | Missing environments cause package promotion failures |
|  | **Security Groups***(referenced but not migrated automatically)* | **-** | Control who can approve/act in workflows | Must exist in all instances so workflows and requests run correctly |
| **Functional (Frequently Migrated)** | **Workflows** | **9** | Define process flows for requests/projects | Safely replace once baseline is in place |
|  | **Request Types** | **19** | Define request forms + link to workflows | Core to business process; promote with replace-once baseline is stable |
|  | **Report Types** | **17** | Define parameterized reports | Frequently updated; safe to always replace |
|  | **Portlet Definitions** | **509** | Define dashboard widgets | Can be promoted anytime; low risk if baseline is aligned |
|  | **Dashboard Modules** | **470** | Define dashboard pages & layouts | Safe to migrate continuously |
|  | **Dashboard Data Sources** | **505** | SQL queries behind portlets | Versioned and replaceable |
|  | **Overview Page Sections** | **61** | Define what appears on overview pages | Safe to promote whenever layout changes |
|  | **Work Plan Templates** | **522** | Define standard project task breakdowns | Migrated when template changes are approved |
|  | **Project Types** | **521** | Define project templates, policies, lifecycle | Promote during process or template changes |
|  | **Program Types** | **901** | Define program-level structure | Migrated when program governance changes |
|  | **Portfolio Types** | **903** | Define portfolio containers and hierarchy | Add – supported entity; safe to promote |
|  | **OData Data Sources** | **906** | Define OData-backed queries | Add – supported;**OData links are not migrated** |
|  | **Custom Menu** | **907** | Define custom UI menu entries | Add – UI extension; safe to promote |
|  | **Chatbot Intent** | **908** | Define chatbot intents*(25.2 +)* | Add – optional; for chatbot-enabled environments |
|  | **PPM Integration SDK** | **9900** | Define PPM integration SDK objects | Add – stable but script-supported; promote if used |

## Summary

- **Baseline Entities:**
    
    These must be version-controlled and aligned across all instances **before** you enable automated or continuous deployment.
    
    Changing them mid-flight without governance can break downstream workflows, requests, or projects.
    
- **Functional Entities = Deployment Payload:**
    
    These are the ones you change frequently — workflows, request types, reports, dashboards, and templates.
    
    Once the baseline is stable, you can safely run “replace existing” migrations for these any time — enabling **predictable, repeatable, on-demand deployments**.
    

---

## 1. **Baseline-First Approach**

- **Foundational entities (baseline)** are migrated **once per alignment cycle**:
    - Use `Replace Existing = ON` for all baseline entities
    - Use `Add Missing` flags **ON** only for the first baseline sync (bootstrapping lower environments)
    - Turn them **OFF** after alignment — if something is missing later, that signals an upstream baseline drift

This establishes a **clean foundation**. After that, baseline entities should only change through controlled governance updates.

## 2. **Functional Entities = Always Replace**

Once baseline is stable:

- For workflows, request types, reports, dashboards, etc.:
    - **Replace Existing = ON** always
    - **Add Missing Environments/Statuses/Security Groups = OFF** (they should already exist from baseline)
    - **Preview Import = ON** in lower environments (optional), OFF in production for speed

This allows **continuous, idempotent deployments**:

- Same package → same result every time
- No manual toggling or environmental exceptions

---

## 3. **Flag Policy Matrix (Standard Default)**

| **Entity Category** | **Replace Existing?** | **Add Missing Environments?** | **Add Missing Statuses?** | **Add Missing Security Groups?** |
| --- | --- | --- | --- | --- |
| **Baseline** | ON (for sync cycles) | ON (bootstrap only), then OFF | ON (bootstrap only), then OFF | ON (bootstrap only), then OFF |
| **Functional (workflows, request types, reports, dashboards)** | ON (always) | OFF | OFF (should be part of baseline) | OFF (should be part of baseline) |

## 4. **kMigratorExtract.sh Script Reference**

This script is used for entity migration in OpenText PPM with the following required parameters:

**Official Documentation:** [OpenText PPM kMigrator Reference](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm)

| **Parameter** | **Description** |
| --- | --- |
| **username** | <Username> |
| **action** | <Search>, <Bundle>, <Test> |
| **referenceCode** | <Reference_Code> |
| **entityId** | <Entity_Id> (see table below) |

### **Entity ID Reference**

| **ID** | **Entity** |
| --- | --- |
| 4 | Environment |
| 9 | Workflow |
| 11 | Special Command |
| 13 | Validation |
| 17 | Report Type |
| 19 | Request Type |
| 26 | Object Type |
| 37 | User Data Context |
| 39 | Request Header Type |
| 58 | Environment Group |
| 61 | Overview Page Section |
| 470 | Module |
| 505 | Data Source |
| 509 | Portlet Definition |
| 521 | Project Type |
| 522 | Workplan Template |
| 901 | Program Type |
| 903 | Portfolio Type |
| 906 | OData Data Source* |
| 907 | Custom Menu |
| 908 | Chatbot Intent (25.2+) |
| 9900 | PPM Integration SDK |
- Note: When using this script to migrate OData data sources, any OData links defined for the OData data sources are not migrated.

### **Optional Parameters**

| **Parameter** | **Description** |
| --- | --- |
| url | <URL> |
| password | <Password> |
| delimiter | <Delimiter> |
| quiet | Runs without verbose output |
| keyword | <Keyword> |
| primaryKey | <Primary_Key> |
| primaryKeyName | <Primary_Key_Name> |
| filename | <File_Name> |
| uncompressed | Outputs uncompressed files |

## 4. **kMigratorImport.sh Script Reference**

Use the [kMigratorImport.sh](http://kMigratorImport.sh) script to migrate OpenText PPM entities. Type only Y or N for the 25 flags listed.

Note: You can also migrate PPM entities from one instance to another from the web UI. For details, see Migrate entities from web UI.

### Example

To import a file, run the command:

```bash
sh ./kMigratorImport.sh -username <Username> -password <Password> -action import -filename <'Full_File_Path'> -i18n none -refdata nochange -flags NNNNNNNNNNYYNNNNNNNNNNN

```

- Caution: Make sure that the full file path is enclosed in single quotes.

### Required Parameters

| **Parameter** | **Description** |
| --- | --- |
| username | <username> |
| action | <import, trial> |
| filename | <filename> |
| i18n | <none, charset, locale> |
|  | none: Require same language and character set
charset: Ignore language and character set warnings
locale: Ignore all warnings |
| refdata | <nochange, install> |
|  | nochange: Do not change reference data
install: Install reference data |
| flags | **`<flags>`** |revi

### Flags Reference

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

Note: If you want to replace the existing portfolio type, you should also replace the existing module (set the Flag 16 to Y).

| Flag 23 | Replace existing PPM Integration SDK |
| --- | --- |
| Flag 24 | Replace existing menu |

Note: This flag is ignored. The existing menu is always replaced, regardless of whether Y or N is specified.

| Flag 25 | Replace existing Chatbot intents (Available for 25.2 and later) |
| --- | --- |

Note: If you want to replace existing Chatbot intents, you should also replace the existing report type (set the Flag 7 to Y).

### Optional Parameters

| **Parameter** | **Description** |
| --- | --- |
| url | <URL> |
| password | <Password> |
| report | <Report> |
| ignorePpmVersionDifference | If you add this parameter in the command line, when a difference of PPM version is detected, PPM continues to import the entity and records the version difference in the execution log. Use with caution as this parameter can be used only when the entity to be imported has no significant data model changes between versions. |