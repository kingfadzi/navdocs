# Migration Guide: Vault-Retrieve Component Refactoring

This guide helps you migrate from the old project-include pattern to the new GitLab CI Component architecture for the vault-secret-fetcher.

## Table of Contents

1. [Overview](#overview)
2. [What Changed](#what-changed)
3. [Migration Strategy: Static Multi-Include](#migration-strategy-static-multi-include)
4. [Step-by-Step Migration](#step-by-step-migration)
5. [Examples](#examples)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)

---

## Overview

The vault-secret-fetcher has been migrated to GitLab's official CI/CD Component architecture, which provides:
- ✅ Semantic versioning support
- ✅ Input validation at parse time
- ✅ Component catalog integration
- ✅ Cleaner, more maintainable syntax

However, this new architecture has a **key limitation**: each component include supports **only ONE Vault role**.

If your pipeline needs **multiple Vault roles** (e.g., fetching from both `ppm-dev` and `s3-read` in the same job), you must include the component **multiple times** and extend multiple anchors.

---

## What Changed

### Old Syntax (Project Include with VAULT_CONFIGS)

```yaml
include:
  - project: 'staging/vault-secret-fetcher'
    file: '/vault-retrieve.yml'

.vault_dynamic:
  extends: .vault_retrieve
  variables:
    VAULT_CONFIGS: |
      - VAULT_ROLE: ppm-dev
        VAULT_PATH: secret/data/ppm/dev/useast
      - VAULT_ROLE: s3-read
        VAULT_PATH: secret/data/shared/s3

deploy:
  extends: .vault_dynamic
  script:
    - echo "Both roles' secrets are available"
```

**Features:**
- ✅ Multiple roles in single extend
- ✅ Dynamic VAULT_CONFIGS via Python script
- ✅ PREFIX and REQUIRED fields supported

---

### New Syntax (Component with Static Multi-Include)

```yaml
include:
  # Include component once per role
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-dev'
      vault_role: 'ppm-dev'
      vault_secret_paths:
        - 'secret/data/ppm/dev/useast'

  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-s3'
      vault_role: 's3-read'
      vault_secret_paths:
        - 'secret/data/shared/s3'

deploy:
  extends:
    - .vault-ppm-dev
    - .vault-s3
  script:
    - echo "Both roles' secrets are available"
```

**Features:**
- ✅ One role per component include
- ✅ Multiple anchors can be extended in jobs
- ✅ Semantic versioning
- ❌ VAULT_CONFIGS YAML format no longer supported
- ❌ PREFIX field removed
- ❌ REQUIRED field removed

---

## Migration Strategy: Static Multi-Include

### Core Concept

**Before:** Dynamically generate multi-role YAML at runtime
**After:** Pre-define all possible roles at parse time, extend the ones you need

### Pattern

1. **Define all Vault roles** your project uses in `include:` section
2. Each role gets its own **component include** with unique `anchor_name`
3. **Jobs extend** the appropriate anchor(s) based on their needs
4. For **dynamic role selection**, use GitLab rules or multiple job variants

---

## Step-by-Step Migration

### Step 1: Inventory Your Vault Roles

List all Vault roles your pipeline uses. Common patterns:

**Environment-based:**
- `ppm-dev`, `ppm-test`, `ppm-staging`, `ppm-prod`

**Service-based:**
- `s3-read`, `smtp-read`, `database-read`

**Example inventory:**
```
ppm-dev       → secret/data/ppm/dev/useast
ppm-test      → secret/data/ppm/test/useast
ppm-staging   → secret/data/ppm/staging/useast
ppm-prod      → secret/data/ppm/prod/useast
s3-read       → secret/data/shared/s3
smtp-read     → secret/data/shared/smtp
```

### Step 2: Map Roles to Secret Paths

For each role, determine which secret paths it accesses:

| Role | Secret Path(s) | Notes |
|------|---------------|-------|
| ppm-dev | `secret/data/ppm/dev/useast` | Main app secrets |
| ppm-dev | `secret/data/ppm/dev/database` | (Optional) DB credentials |
| s3-read | `secret/data/shared/s3` | MinIO/S3 access |
| smtp-read | `secret/data/shared/smtp` | Email service |

### Step 3: Convert to Component Includes

Replace your old project include with component includes:

```yaml
include:
  # PPM Development Environment
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-dev'
      vault_role: 'ppm-dev'
      vault_secret_paths:
        - 'secret/data/ppm/dev/useast'
        - 'secret/data/ppm/dev/database'  # Multiple paths for same role

  # PPM Test Environment
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-test'
      vault_role: 'ppm-test'
      vault_secret_paths:
        - 'secret/data/ppm/test/useast'

  # PPM Staging Environment
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-staging'
      vault_role: 'ppm-staging'
      vault_secret_paths:
        - 'secret/data/ppm/staging/useast'

  # PPM Production Environment
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-prod'
      vault_role: 'ppm-prod'
      vault_secret_paths:
        - 'secret/data/ppm/prod/useast'

  # Shared Services
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-s3'
      vault_role: 's3-read'
      vault_secret_paths:
        - 'secret/data/shared/s3'

  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-smtp'
      vault_role: 'smtp-read'
      vault_secret_paths:
        - 'secret/data/shared/smtp'
```

**Notes:**
- `anchor_name`: Creates `.vault-ppm-dev`, `.vault-s3`, etc.
- `vault_role`: Single Vault role (no arrays)
- `vault_secret_paths`: JSON array of paths (can have multiple paths per role)
- Component URL uses your GitLab FQDN and project path

### Step 4: Update Job Definitions

**Pattern A: Static Role Assignment**

Use when the role is known at pipeline definition time:

```yaml
# Before
extract:
  extends: .vault_dynamic_base
  before_script:
    - export VAULT_CONFIGS="$(python3 tools/setup_vault_configs.py $BOM_FILE extract)"
    - !reference [.vault_retrieve, before_script]

# After
extract:
  extends:
    - .vault-ppm-dev    # Fixed role
    - .vault-s3         # Can extend multiple anchors
  stage: extract
  before_script:
    - dnf install -y -q git bash openssh-clients sshpass
    - # Your existing setup without Vault config generation
  script:
    - python3 tools/deploy.py extract --type $DEPLOYMENT_TYPE --bom $BOM_FILE
```

**Pattern B: Dynamic Role Selection with Rules**

Use when the role depends on pipeline variables:

```yaml
# Separate jobs for each environment
extract:dev:
  extends:
    - .vault-ppm-dev
    - .vault-s3
  stage: extract
  script:
    - python3 tools/deploy.py extract
  rules:
    - if: '$SOURCE_ENV == "dev"'

extract:test:
  extends:
    - .vault-ppm-test
    - .vault-s3
  stage: extract
  script:
    - python3 tools/deploy.py extract
  rules:
    - if: '$SOURCE_ENV == "test"'

extract:prod:
  extends:
    - .vault-ppm-prod
    - .vault-s3
  stage: extract
  script:
    - python3 tools/deploy.py extract
  rules:
    - if: '$SOURCE_ENV == "prod"'
```

**Pattern C: Use Job Templates with Rules**

Create reusable templates:

```yaml
.extract_template:
  stage: extract
  before_script:
    - dnf install -y -q git bash openssh-clients sshpass
    - dnf module reset -y python36
    - dnf install -y -q python3.11 python3.11-pip python3.11-devel
    - pip3.11 install PyYAML boto3 --quiet
  script:
    - python3 tools/deploy.py extract --type $DEPLOYMENT_TYPE --bom $BOM_FILE
  artifacts:
    paths:
      - bundles/*.yaml
    expire_in: 1 hour

extract:dev:
  extends:
    - .extract_template
    - .vault-ppm-dev
    - .vault-s3
  rules:
    - if: '$BOM_FILE =~ /dev/'

extract:test:
  extends:
    - .extract_template
    - .vault-ppm-test
    - .vault-s3
  rules:
    - if: '$BOM_FILE =~ /test/'

extract:prod:
  extends:
    - .extract_template
    - .vault-ppm-prod
    - .vault-s3
  rules:
    - if: '$BOM_FILE =~ /prod/'
```

### Step 5: Remove VAULT_CONFIGS Generation

If you had a Python script generating `VAULT_CONFIGS`, you have two options:

**Option A: Remove it entirely**
- Hardcode role selection in pipeline YAML using rules
- Simplest approach if role logic is straightforward

**Option B: Adapt it for job selection**
- Change script to output which **job** to run instead of which role
- Use GitLab's dynamic child pipelines

```yaml
# Generate child pipeline that includes appropriate jobs
generate-pipeline:
  stage: .pre
  script:
    - python3 tools/generate_pipeline.py $BOM_FILE > child-pipeline.yml
    - cat child-pipeline.yml
  artifacts:
    paths:
      - child-pipeline.yml

trigger-deployment:
  stage: deploy
  trigger:
    include:
      - artifact: child-pipeline.yml
        job: generate-pipeline
```

**Option C: Keep for other purposes**
- If script does more than Vault config, keep it
- Just remove the `VAULT_CONFIGS` export and `!reference` call

---

## Examples

### Example 1: Simple Single-Environment Pipeline

**Scenario:** Always deploy to dev environment

```yaml
include:
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-dev'
      vault_role: 'ppm-dev'
      vault_secret_paths:
        - 'secret/data/ppm/dev/useast'

stages:
  - deploy

deploy:
  extends: .vault-ppm-dev
  stage: deploy
  script:
    - echo "PPM_URL: $PPM_URL"
    - echo "Deploying to dev..."
```

---

### Example 2: Multi-Environment Pipeline with Manual Selection

**Scenario:** User selects environment via pipeline variable

```yaml
include:
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-dev'
      vault_role: 'ppm-dev'
      vault_secret_paths:
        - 'secret/data/ppm/dev/useast'

  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-prod'
      vault_role: 'ppm-prod'
      vault_secret_paths:
        - 'secret/data/ppm/prod/useast'

stages:
  - deploy

deploy:dev:
  extends: .vault-ppm-dev
  stage: deploy
  script:
    - ./deploy.sh dev
  rules:
    - if: '$TARGET_ENV == "dev"'

deploy:prod:
  extends: .vault-ppm-prod
  stage: deploy
  script:
    - ./deploy.sh prod
  rules:
    - if: '$TARGET_ENV == "prod"'
  when: manual
```

---

### Example 3: Extract-Import-Archive Pattern (Your Use Case)

**Scenario:** Extract from source server, import to target server, archive on target

```yaml
include:
  # All possible environment roles
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-dev'
      vault_role: 'ppm-dev'
      vault_secret_paths:
        - 'secret/data/ppm/dev/useast'

  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-test'
      vault_role: 'ppm-test'
      vault_secret_paths:
        - 'secret/data/ppm/test/useast'

  # Shared S3 for all environments
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-s3'
      vault_role: 's3-read'
      vault_secret_paths:
        - 'secret/data/shared/s3'

stages:
  - extract
  - import
  - archive

variables:
  DEPLOYMENT_TYPE: "baseline"
  SOURCE_ENV: "dev"
  TARGET_ENV: "test"

# Base job templates
.job_base:
  image: almalinux:8
  before_script:
    - dnf install -y -q git bash openssh-clients sshpass
    - dnf module reset -y python36
    - dnf install -y -q python3.11 python3.11-pip python3.11-devel
    - pip3.11 install PyYAML boto3 --quiet
    - ln -sf /usr/bin/python3.11 /usr/bin/python3

# Extract from source environment
extract:
  extends:
    - .job_base
    - .vault-ppm-dev    # Source environment (change based on SOURCE_ENV)
    - .vault-s3         # S3 for file operations
  stage: extract
  script:
    - python3 tools/deploy.py extract --type $DEPLOYMENT_TYPE
  artifacts:
    paths:
      - bundles/*.yaml
    expire_in: 1 hour
  rules:
    - if: '$SOURCE_ENV == "dev"'

# Import to target environment
import:
  extends:
    - .job_base
    - .vault-ppm-test   # Target environment (change based on TARGET_ENV)
    - .vault-s3
  stage: import
  script:
    - python3 tools/deploy.py import --type $DEPLOYMENT_TYPE
  needs: [extract]
  rules:
    - if: '$TARGET_ENV == "test"'

# Archive on target environment
archive:
  extends:
    - .job_base
    - .vault-ppm-test   # Target environment
    - .vault-s3
  stage: archive
  script:
    - python3 tools/deploy.py archive --type $DEPLOYMENT_TYPE
  needs: [extract, import]
  artifacts:
    paths:
      - archives/*.yaml
      - evidence/
    expire_in: 1 year
  rules:
    - if: '$TARGET_ENV == "test"'
```

**To support dynamic SOURCE_ENV/TARGET_ENV:**

Create job variants for each combination:

```yaml
# Extract jobs (one per source environment)
extract:from-dev:
  extends:
    - .job_base
    - .vault-ppm-dev
    - .vault-s3
  stage: extract
  script:
    - python3 tools/deploy.py extract
  artifacts:
    paths:
      - bundles/*.yaml
    expire_in: 1 hour
  rules:
    - if: '$SOURCE_ENV == "dev"'

extract:from-test:
  extends:
    - .job_base
    - .vault-ppm-test
    - .vault-s3
  stage: extract
  script:
    - python3 tools/deploy.py extract
  artifacts:
    paths:
      - bundles/*.yaml
    expire_in: 1 hour
  rules:
    - if: '$SOURCE_ENV == "test"'

# Import jobs (one per target environment)
import:to-dev:
  extends:
    - .job_base
    - .vault-ppm-dev
    - .vault-s3
  stage: import
  script:
    - python3 tools/deploy.py import
  needs:
    - job: extract:from-dev
      optional: true
    - job: extract:from-test
      optional: true
  rules:
    - if: '$TARGET_ENV == "dev"'

import:to-test:
  extends:
    - .job_base
    - .vault-ppm-test
    - .vault-s3
  stage: import
  script:
    - python3 tools/deploy.py import
  needs:
    - job: extract:from-dev
      optional: true
    - job: extract:from-test
      optional: true
  rules:
    - if: '$TARGET_ENV == "test"'
```

---

### Example 4: Using BOM File to Determine Roles

**Scenario:** BOM file specifies source and target servers

```yaml
include:
  # All possible roles...
  - component: '...'

stages:
  - determine
  - extract
  - import

# Parse BOM and determine which jobs to run
determine:roles:
  stage: determine
  script:
    - SOURCE_ROLE=$(python3 tools/parse_bom.py $BOM_FILE --get-source-role)
    - TARGET_ROLE=$(python3 tools/parse_bom.py $BOM_FILE --get-target-role)
    - echo "SOURCE_ROLE=$SOURCE_ROLE" >> build.env
    - echo "TARGET_ROLE=$TARGET_ROLE" >> build.env
  artifacts:
    reports:
      dotenv: build.env

# Then create job variants that use the determined roles
extract:
  extends:
    - .vault-ppm-dev  # You still need to match this to SOURCE_ROLE
  stage: extract
  script:
    - python3 tools/deploy.py extract
  needs: [determine:roles]
  rules:
    - if: '$SOURCE_ROLE == "ppm-dev"'
```

**Note:** This still requires creating job variants. For fully dynamic role selection, consider using **dynamic child pipelines** (see Advanced Patterns below).

---

## Advanced Patterns

### Pattern: Dynamic Child Pipelines

For truly dynamic role selection based on BOM files, generate a child pipeline:

**Step 1: Create generator script** (`tools/generate_deployment_pipeline.py`)

```python
#!/usr/bin/env python3
import yaml
import sys

def generate_pipeline(bom_file):
    # Parse BOM to determine source and target roles
    with open(bom_file) as f:
        bom = yaml.safe_load(f)

    source_env = bom['source_server']['environment']  # e.g., "dev"
    target_env = bom['target_server']['environment']  # e.g., "test"

    # Generate pipeline YAML with appropriate extends
    pipeline = {
        'stages': ['extract', 'import', 'archive'],
        'extract': {
            'extends': [
                '.job_base',
                f'.vault-ppm-{source_env}',
                '.vault-s3'
            ],
            'stage': 'extract',
            'script': ['python3 tools/deploy.py extract'],
            'artifacts': {
                'paths': ['bundles/*.yaml'],
                'expire_in': '1 hour'
            }
        },
        'import': {
            'extends': [
                '.job_base',
                f'.vault-ppm-{target_env}',
                '.vault-s3'
            ],
            'stage': 'import',
            'script': ['python3 tools/deploy.py import'],
            'needs': ['extract']
        },
        'archive': {
            'extends': [
                '.job_base',
                f'.vault-ppm-{target_env}',
                '.vault-s3'
            ],
            'stage': 'archive',
            'script': ['python3 tools/deploy.py archive'],
            'needs': ['extract', 'import'],
            'artifacts': {
                'paths': ['archives/*.yaml', 'evidence/'],
                'expire_in': '1 year'
            }
        }
    }

    print(yaml.dump(pipeline, default_flow_style=False))

if __name__ == '__main__':
    generate_pipeline(sys.argv[1])
```

**Step 2: Main pipeline generates and triggers child**

```yaml
include:
  # Include all possible component variants
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-dev'
      vault_role: 'ppm-dev'
      vault_secret_paths:
        - 'secret/data/ppm/dev/useast'

  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-ppm-test'
      vault_role: 'ppm-test'
      vault_secret_paths:
        - 'secret/data/ppm/test/useast'

  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-s3'
      vault_role: 's3-read'
      vault_secret_paths:
        - 'secret/data/shared/s3'

stages:
  - prepare
  - deploy

variables:
  BOM_FILE: "bom-files/baseline-dev-to-test.yaml"

# Base job template that all generated jobs will extend
.job_base:
  image: almalinux:8
  before_script:
    - dnf install -y -q git bash openssh-clients sshpass python3.11
    - pip3.11 install PyYAML boto3 --quiet

generate:pipeline:
  stage: prepare
  image: almalinux:8
  before_script:
    - dnf install -y -q python3.11 python3.11-pip
    - pip3.11 install PyYAML
  script:
    - python3 tools/generate_deployment_pipeline.py $BOM_FILE > child-pipeline.yml
    - echo "Generated pipeline:"
    - cat child-pipeline.yml
  artifacts:
    paths:
      - child-pipeline.yml

deploy:
  stage: deploy
  trigger:
    include:
      - artifact: child-pipeline.yml
        job: generate:pipeline
    strategy: depend
```

**This approach:**
- ✅ Fully dynamic based on BOM
- ✅ Uses component architecture
- ✅ No job duplication in main pipeline
- ⚠️ More complex setup
- ⚠️ Harder to debug (two pipelines)

---

## Troubleshooting

### Issue: "component could not be found"

**Problem:** GitLab can't find your component

**Solutions:**
1. Verify component URL format:
   ```yaml
   component: 'gitlab.example.com/group/project/component-name@version'
   ```
2. Check component is published (CI/CD > Components)
3. Verify you have access to the repository
4. Use `@main` or `@$CI_COMMIT_SHA` for testing

---

### Issue: "Input 'anchor_name' is required"

**Problem:** Missing required input in component include

**Solution:** Ensure all three inputs are provided:
```yaml
- component: '...'
  inputs:
    anchor_name: 'vault-my-role'      # Required
    vault_role: 'my-role'              # Required
    vault_secret_paths:                # Required (even if empty)
      - 'secret/data/path'
```

---

### Issue: Secrets not available in job

**Problem:** Job doesn't extend vault anchor

**Solutions:**
1. Check job extends the correct anchor:
   ```yaml
   my-job:
     extends: .vault-ppm-dev  # Must match anchor_name in component include
   ```
2. Verify anchor name has leading dot: `.vault-ppm-dev` (component creates it automatically)
3. Check secrets exist in Vault at the specified path
4. Verify role has permission to read the path

---

### Issue: "Failed to authenticate to Vault"

**Problem:** Role doesn't exist or bound_claims don't match

**Solutions:**
1. Verify role exists: `vault read auth/jwt/role/my-role`
2. Check bound_claims match your project:
   ```
   bound_claims: map[project_id:153]
   ```
3. Verify `CI_JOB_JWT` is available (check GitLab version and settings)
4. Check Vault is accessible from GitLab Runner

---

### Issue: Need to use different secret paths per pipeline run

**Problem:** Component inputs are static at parse time

**Solutions:**
1. **Create multiple component includes** with different paths
2. **Use rules** to select appropriate job variant
3. **Use dynamic child pipelines** (see Advanced Patterns)
4. **Keep old project include** if truly dynamic paths are critical

---

## FAQ

### Q: Can I still use VAULT_CONFIGS YAML format?

**A:** No, the new component doesn't support it. You must:
- Include component once per role
- Extend multiple anchors if you need multiple roles

### Q: What happened to PREFIX field?

**A:** It was removed in the component migration. If you need prefixed keys:
- Store secrets with prefixes already applied in Vault
- Or post-process secrets in your job script

### Q: What happened to REQUIRED field?

**A:** It was removed. All secret fetches must succeed. For optional secrets:
- Use separate jobs with `allow_failure: true`
- Or use rules to conditionally run jobs

### Q: Can I use both old and new syntax in same project?

**A:** Yes, you can mix:
```yaml
include:
  # Old style
  - project: 'staging/vault-secret-fetcher'
    file: '/vault-retrieve.yml'

  # New style
  - component: 'eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@1.0.0'
    inputs:
      anchor_name: 'vault-new'
      vault_role: 'my-role'
      vault_secret_paths: ['secret/data/path']
```

This is useful for gradual migration.

### Q: How do I test component changes before committing?

**A:** Use local includes:
```yaml
include:
  - local: 'templates/vault-retrieve.yml'
    inputs:
      anchor_name: 'test'
      vault_role: 'test-role'
      vault_secret_paths: ['secret/data/test']
```

### Q: Should I migrate to the new component?

**A:** Consider:

**Migrate if:**
- ✅ You want semantic versioning
- ✅ Your role selection is relatively static
- ✅ You can use rules or multiple job definitions
- ✅ You want cleaner syntax

**Stay on old include if:**
- ✅ You heavily rely on dynamic multi-role selection
- ✅ You use PREFIX or REQUIRED fields extensively
- ✅ Migration effort is too high right now
- ✅ Current solution works fine

### Q: Can I contribute PREFIX/REQUIRED back to the component?

**A:** Yes! The component is open source. You can:
1. Fork the vault-secret-fetcher repository
2. Add features to `scripts/vault-fetch-kv.sh`
3. Update component spec in `templates/vault-retrieve.yml`
4. Submit merge request

---

## Summary Checklist

Use this checklist when migrating:

- [ ] Inventory all Vault roles your pipeline uses
- [ ] Map each role to its secret paths
- [ ] Replace project include with component includes (one per role)
- [ ] Update job definitions to extend appropriate anchors
- [ ] Remove VAULT_CONFIGS generation (or adapt for other purposes)
- [ ] Remove !reference calls to vault fetcher's before_script
- [ ] Handle dynamic role selection (rules, job variants, or child pipelines)
- [ ] Test in dev environment first
- [ ] Update documentation for your team
- [ ] Verify all secrets are accessible in jobs
- [ ] Check artifacts and job outputs are correct

---

## Getting Help

If you encounter issues during migration:

1. Check functional tests in vault-secret-fetcher repo: `tests/functional-tests.yml`
2. Review examples in `examples/` directory
3. Consult main README: `README.md`
4. Open an issue in vault-secret-fetcher repository

---

## Document Version

- **Version:** 1.0.0
- **Date:** 2025-10-21
- **Component Version:** 1.0.0
- **Author:** vault-secret-fetcher team
