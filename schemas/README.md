# BOM Schema Validation

This directory contains JSON Schema files that validate BOM (Bill of Materials) structure and entity types.

---

## Overview

**Purpose:** Ensure BOMs are correctly structured before deployment starts.

**Validation happens:**
- In CI/CD pipeline (validate stage)
- In CLI commands (`python3 -m tools.config.validation`)
- Before extraction begins

**Benefits:**
- Catch errors early (before touching PPM servers)
- Validate entity IDs match category (baseline vs functional)
- Enforce mandatory fields (category, referenceCode, etc.)
- Ensure reference codes follow naming convention

---

## Files

### bom-baseline-schema.json

Validates baseline BOMs (infrastructure entities).

**Enforces:**
- `category: baseline` (required)
- `entities` list (required, minimum 1 entity)
- Entity IDs limited to: 4, 11, 13, 26, 37, 39, 58
- Each entity requires `id` and `reference_code`
- Reference codes must be UPPERCASE_WITH_UNDERSCORES

**Example valid entity:**
```yaml
- id: 26
  reference_code: "OBJ_CUSTOM_ASSET"
  name: "Custom Asset Object Type"  # optional
```

---

### bom-functional-schema.json

Validates functional BOMs (business logic entities).

**Enforces:**
- `category: functional` (required)
- `entities` list (required, minimum 1 entity)
- Entity IDs limited to: 9, 17, 19, 61, 470, 505, 509, 521, 522, 901, 903, 906, 907, 908, 9900
- Each entity requires `id` and `reference_code`
- Reference codes must be UPPERCASE_WITH_UNDERSCORES

**Example valid entity:**
```yaml
- id: 9
  reference_code: "WF_INCIDENT_MGMT"
  name: "Incident Management Workflow"  # optional
```

---

### entity-types.yaml

**Not a schema** - Reference documentation listing all valid entity types.

**Contains:**
- Entity type descriptions
- Example reference codes
- Notes about special considerations

**Use for:** Understanding what entity types are available and how to name them.

---

## How JSON Schema Works

### What is JSON Schema?

Industry-standard format for describing and validating JSON/YAML structure.

**Learn more:** [json-schema.org](https://json-schema.org/)

### Reading Schema Files

**Basic structure:**
```json
{
  "properties": {
    "category": {
      "type": "string",
      "enum": ["baseline"]  // Only "baseline" allowed
    },
    "entities": {
      "type": "array",
      "items": {
        "properties": {
          "id": {
            "type": "integer",
            "enum": [4, 11, 13, 26, 37, 39, 58]  // Only these IDs allowed
          },
          "reference_code": {
            "pattern": "^[A-Z0-9_]+$"  // UPPERCASE with underscores
          }
        }
      }
    }
  }
}
```

**Key concepts:**
- `type` - Data type (string, integer, array, etc.)
- `enum` - List of allowed values
- `pattern` - Regular expression for string validation
- `required` - Fields that must be present
- `minItems` - Minimum array length

---

## Validation Examples

### Valid Baseline BOM
```yaml
version: "1.0"
category: baseline
profile: baseline
source_server: dev-ppm-useast
target_server: test-ppm-useast
entities:
  - id: 26
    reference_code: "OBJ_CUSTOM_ASSET"
```
✅ **PASSES** - Category matches, entity ID valid, reference code uppercase

---

### Invalid Baseline BOM (Wrong Category)
```yaml
version: "1.0"
category: functional  # ❌ WRONG
profile: baseline
entities:
  - id: 26
    reference_code: "OBJ_CUSTOM_ASSET"
```
❌ **FAILS** - Schema validation: profile "baseline" requires category "baseline"

---

### Invalid Baseline BOM (Wrong Entity ID)
```yaml
version: "1.0"
category: baseline
profile: baseline
entities:
  - id: 9  # ❌ WRONG - Workflow is functional, not baseline
    reference_code: "WF_TEST"
```
❌ **FAILS** - Schema validation: 9 is not in [4, 11, 13, 26, 37, 39, 58]

---

### Invalid Functional BOM (Missing referenceCode)
```yaml
version: "2.0"
category: functional
profile: functional-cd
entities:
  - id: 9
    name: "Workflow"
    # ❌ Missing reference_code
```
❌ **FAILS** - Schema validation: 'reference_code' is a required property

---

### Invalid BOM (Lowercase reference code)
```yaml
version: "2.0"
category: functional
profile: functional-cd
entities:
  - id: 9
    reference_code: "wf_incident_mgmt"  # ❌ Lowercase not allowed
```
❌ **FAILS** - Schema validation: does not match '^[A-Z0-9_]+$'

---

## Testing Validation

**Validate a BOM manually:**
```bash
python3 -m tools.config.validation --file boms/baseline.yaml
```

**Example output (valid):**
```
=== BOM VALIDATION (JSON Schema + Governance Rules) ===
File: boms/baseline.yaml

✓ [OK] BOM is valid
  - Schema validation: PASSED
  - Governance rules: PASSED

=== RESULT: PASSED ===
```

**Example output (invalid):**
```
=== BOM VALIDATION (JSON Schema + Governance Rules) ===
File: boms/baseline.yaml

✗ [FAILED] BOM validation failed
  - Schema validation failed at 'entities -> 0 -> reference_code':
    'reference_code' is a required property

=== RESULT: FAILED (1 errors) ===
```

---

## Adding New Entity Types

To add support for a new entity type:

1. **Determine category** (baseline or functional)

2. **Update appropriate schema:**
   - Baseline: `bom-baseline-schema.json`
   - Functional: `bom-functional-schema.json`

3. **Add entity ID to enum:**
   ```json
   "enum": [9, 17, 19, 61, 470, 505, 509, 521, 522, 901, 903, 906, 907, 908, 9900, 999]
   //                                                                              ^^^
   //                                                                            new ID
   ```

4. **Update entity-types.yaml:**
   ```yaml
   999:
     name: "New Entity Type"
     description: "What this entity type does"
     example_reference_codes:
       - "NEW_EXAMPLE_1"
       - "NEW_EXAMPLE_2"
   ```

5. **Update ENTITY_REFERENCE.md** documentation

6. **Add profile flag** if needed for replacement behavior

---

## Naming Conventions

### Reference Codes

**Pattern:** `^[A-Z0-9_]+$`

**Format:** CATEGORY_DESCRIPTOR_NAME

**Examples:**
- Workflows: `WF_INCIDENT_MGMT`, `WF_CHANGE_REQUEST`
- Object Types: `OBJ_CUSTOM_ASSET`, `OBJ_SERVICE_CATALOG`
- Validations: `VAL_PRIORITY_LEVELS`, `VAL_STATUS_CODES`
- Request Types: `REQ_TYPE_INCIDENT`, `REQ_TYPE_SERVICE`
- Reports: `RPT_INCIDENT_STATUS`, `RPT_PROJECT_METRICS`

**Why uppercase?**
- Consistency with PPM conventions
- Easier to distinguish from variable names
- Clear in logs and error messages
- Standard practice in enterprise systems

---

## Troubleshooting

### "Schema validation failed at 'category'"
**Problem:** Missing or wrong category field
**Fix:** Add `category: baseline` or `category: functional`

### "does not match '^[A-Z0-9_]+$'"
**Problem:** Reference code has lowercase or special characters
**Fix:** Use only UPPERCASE letters, numbers, and underscores

### "X is not one of [...]"
**Problem:** Entity ID not allowed for this category
**Fix:** Check entity-types.yaml - may be wrong category or invalid ID

### "'reference_code' is a required property"
**Problem:** Missing reference_code field
**Fix:** Add `reference_code: "YOUR_CODE"` to entity

### "Missing required field: category"
**Problem:** BOM doesn't have category field
**Fix:** Add `category: baseline` or `category: functional` at top level

---

## Further Reading

- [JSON Schema Documentation](https://json-schema.org/understanding-json-schema/)
- [JSON Schema Validation Keywords](https://json-schema.org/understanding-json-schema/reference/generic.html)
- [OpenText PPM Entity Types](https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122100_InstallAdmin_Server.htm)
- [entity-types.yaml](entity-types.yaml) - Internal reference
