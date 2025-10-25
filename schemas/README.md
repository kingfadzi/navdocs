# BOM Schema Validation

Validates BOM structure before deployment using industry-standard JSON Schema.

**Validation command:**
```bash
python3 -m tools.config.validation --file boms/baseline.yaml
```

---

## Schema Files

### bom-baseline-schema.json
**Allowed entity IDs:** 4, 11, 13, 26, 37, 39, 58 (infrastructure entities)

### bom-functional-schema.json
**Allowed entity IDs:** 9, 17, 19, 61, 470, 505, 509, 521, 522, 901, 903, 906, 907, 908, 9900 (business logic)

### entity-types.yaml
Reference documentation for entity types (not a validation schema).

---

## Mandatory Fields

**BOM level:** `version`, `category`, `profile`, `source_server`, `target_server`, `entities`

**Entity level:** `id`, `reference_code`

**Reference code pattern:** `^[A-Z0-9_]+$` (UPPERCASE with underscores)

**Examples:** `WF_INCIDENT_MGMT`, `OBJ_CUSTOM_ASSET`, `VAL_PRIORITY_LEVELS`

---

## Adding New Entity Types

1. Add entity ID to `enum` in appropriate schema (baseline or functional)
2. Update `entity-types.yaml` with description and examples
3. Update `ENTITY_REFERENCE.md` documentation
4. Add profile flag if needed for replacement behavior

---

## Common Errors

| Error | Fix |
|-------|-----|
| `'reference_code' is a required property` | Add `reference_code: "YOUR_CODE"` to entity |
| `does not match '^[A-Z0-9_]+$'` | Use UPPERCASE with underscores only |
| `X is not one of [...]` | Entity ID not allowed for this category |
| `Missing required field: category` | Add `category: baseline` or `functional` |
