# Manual Deployment Guide

Quick guide for running deployments manually via CLI.

## Two Modes

**Local (Testing)** - Mock scripts, no real servers
**Remote (Production)** - Real SSH connections, real deployments

Mode is controlled by `DEPLOYMENT_ENV` variable:
- `DEPLOYMENT_ENV=local` -> Local mode
- Not set -> Remote mode

---

## Local Deployment (Testing)

```bash
# 1. Set mode and credentials
export DEPLOYMENT_ENV=local
export PPM_ADMIN_USER=testuser
export PPM_ADMIN_PASSWORD=testpass

# 2. Validate
python3 -m tools.deployment.orchestrator validate --bom boms/functional.yaml

# 3. Deploy
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

**What happens:**
- Mock kMigrator scripts run locally
- Bundles saved to `./bundles/`
- Archive saved to `./archives/`
- No real data transferred

---

## Remote Deployment (Production)

```bash
# 1. Set credentials (NO DEPLOYMENT_ENV!)
export SSH_USERNAME=your_ssh_user
export SSH_PASSWORD=your_ssh_pass
export PPM_ADMIN_USER=your_ppm_user
export PPM_ADMIN_PASSWORD=your_ppm_pass
export AWS_ACCESS_KEY_ID=your_s3_key
export AWS_SECRET_ACCESS_KEY=your_s3_secret

# 2. Validate (IMPORTANT!)
python3 -m tools.deployment.orchestrator validate --bom boms/functional.yaml

# 3. Deploy
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

**What happens:**
- SSH to real PPM servers
- Real kMigrator extracts/imports
- Bundles stored in S3
- Real deployment occurs

---

## Save Credentials (Recommended)

Create credential files instead of typing repeatedly:

```bash
# Local credentials
cat > ~/.ppm_creds_local <<EOF
export DEPLOYMENT_ENV=local
export PPM_ADMIN_USER=testuser
export PPM_ADMIN_PASSWORD=testpass
EOF

# Remote credentials
cat > ~/.ppm_creds_remote <<EOF
export SSH_USERNAME=your_ssh_user
export SSH_PASSWORD=your_ssh_pass
export PPM_ADMIN_USER=your_ppm_user
export PPM_ADMIN_PASSWORD=your_ppm_pass
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
EOF

chmod 600 ~/.ppm_creds_*
```

**Use them:**
```bash
source ~/.ppm_creds_local   # For testing
source ~/.ppm_creds_remote  # For production
```

---

## Available Commands

### validate - Check before deploying
```bash
python3 -m tools.deployment.orchestrator validate --bom boms/functional.yaml
```

### deploy - Full deployment (extract -> import -> archive)
```bash
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

### extract - Phase 1 only
```bash
python3 -m tools.deployment.orchestrator extract --type functional --bom boms/functional.yaml
```

### import - Phase 2 only
```bash
python3 -m tools.deployment.orchestrator import --type functional --bom boms/functional.yaml
```

### archive - Phase 3 only
```bash
python3 -m tools.deployment.orchestrator archive --type functional --bom boms/functional.yaml
```

### rollback - Restore previous deployment
```bash
python3 -m tools.deployment.orchestrator rollback --type functional --bom boms/functional.yaml
```

---

## Complete Examples

### Baseline Deployment (All Entities)
```bash
# Local test
source ~/.ppm_creds_local
python3 -m tools.deployment.orchestrator validate --bom boms/baseline.yaml
python3 -m tools.deployment.orchestrator deploy --type baseline --bom boms/baseline.yaml

# Remote
source ~/.ppm_creds_remote
python3 -m tools.deployment.orchestrator validate --bom boms/baseline.yaml
python3 -m tools.deployment.orchestrator deploy --type baseline --bom boms/baseline.yaml
```

### Functional Deployment (Specific Entities)
```bash
# Local test
source ~/.ppm_creds_local
python3 -m tools.deployment.orchestrator validate --bom boms/functional.yaml
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml

# Remote
source ~/.ppm_creds_remote
python3 -m tools.deployment.orchestrator validate --bom boms/functional.yaml
python3 -m tools.deployment.orchestrator deploy --type functional --bom boms/functional.yaml
```

---

## Troubleshooting

### Credentials not set
```
ERROR: PPM credentials not set in environment
```
**Fix:** Export the required variables or source credentials file

### SSH connection failed
```
ERROR: Remote extraction failed: SSH connection refused
```
**Fix:** Check SSH_USERNAME, SSH_PASSWORD, verify sshpass installed

### Metadata not found
```
ERROR: Metadata file not found: bundles/functional-metadata.yaml
```
**Fix:** Run `extract` before `import`, or use `deploy` command

### S3 access denied
```
ERROR: S3 connection failed: Access Denied
```
**Fix:** Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

---

## Quick Reference

| Command | Purpose | Args |
|---------|---------|------|
| `validate` | Check environment | `--bom <file>` |
| `deploy` | Full deployment | `--type <baseline\|functional> --bom <file>` |
| `extract` | Phase 1 | `--type <baseline\|functional> --bom <file>` |
| `import` | Phase 2 | `--type <baseline\|functional> --bom <file>` |
| `archive` | Phase 3 | `--type <baseline\|functional> --bom <file>` |
| `rollback` | Restore | `--type <baseline\|functional> --bom <file>` |

**Environment Variables:**

| Variable | Local | Remote | Purpose |
|----------|-------|--------|---------|
| `DEPLOYMENT_ENV` | `local` | not set | Mode selector |
| `PPM_ADMIN_USER` | Required | Required | PPM username |
| `PPM_ADMIN_PASSWORD` | Required | Required | PPM password |
| `SSH_USERNAME` | - | Required | SSH user |
| `SSH_PASSWORD` | - | Required | SSH password |
| `AWS_ACCESS_KEY_ID` | - | Required | S3 key |
| `AWS_SECRET_ACCESS_KEY` | - | Required | S3 secret |

---

## Best Practices

1. **Always validate first** - Catch issues before deploying
2. **Test locally** - Use local mode before remote
3. **Use credential files** - Easier and safer
4. **Follow promotion order** - dev -> test -> staging -> prod
5. **Watch output** - Monitor for errors during execution
