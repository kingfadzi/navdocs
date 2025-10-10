## Deployment Information

**Deployment Type:** <!-- baseline / functional / rollback -->

**Target Environment:** <!-- dev / test / prod -->

**Change Request:** <!-- CR-XXXXX or N/A for baseline -->

**BOM File(s):**
<!-- List BOM files being deployed -->
- `boms/...`

**Rollback Plan:**
<!-- For prod deployments, specify rollback pipeline ID or state if none exists -->
- Rollback pipeline ID: `12345` (or "N/A - first deployment")

---

## Checklist

### Pre-Deployment
- [ ] BOM validated locally (`python3 tools/validate_bom.py --file boms/...`)
- [ ] BOM tested in lower environment (dev for test, test for prod)
- [ ] Required approvals obtained (2 for non-prod, 3+ for prod)
- [ ] For baseline: Platform team notified
- [ ] For prod: Change request approved (if functional)

### BOM Content Review
- [ ] All required fields present
- [ ] Version follows semantic versioning (X.Y.Z)
- [ ] Profile exists and is correct
- [ ] Entity IDs and reference codes are correct
- [ ] `rollback_pipeline_id` specified (for prod)

### Post-Merge (Automated)
- [ ] BOM validation passed
- [ ] Review approved (prod only)
- [ ] Deployment succeeded (extract → import → archive)

---

## Additional Notes
<!-- Add any special instructions, dependencies, or context -->

---

## Approval Requirements

| Environment | MR Approvals | Pipeline Gate | Total |
|-------------|--------------|---------------|-------|
| Dev | 2 | None | 2 |
| Test | 2 | None | 2 |
| Prod | 3+ | Manual review | 4+ |

**Baseline deployments:** Must include approval from @platform-team

---

## Rollback Procedure

If this deployment fails:
1. Create rollback BOM pointing to previous pipeline ID (copy from GitLab pipeline URL)
2. Follow same approval process
3. Merge to trigger rollback pipeline

---

/label ~deployment
<!-- Add additional labels: ~baseline, ~functional, ~rollback, ~prod, ~test, ~dev -->

