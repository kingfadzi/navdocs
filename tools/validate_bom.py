#!/usr/bin/env python3
"""
BOM Validation Script
Validates BOM files for schema compliance and required fields
"""

import sys
import yaml
import re
import os
from pathlib import Path
import argparse
import subprocess


def load_yaml(file_path):
    """Load YAML file safely."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def load_config():
    """Load deployment config."""
    root = Path(__file__).parent.parent
    config_file = root / 'config' / 'deployment-config.yaml'
    return load_yaml(config_file)


def load_rules():
    """Load governance rules."""
    root = Path(__file__).parent.parent
    rules_file = root / 'config' / 'rules.yaml'
    if not rules_file.exists():
        return {}  # No rules file = no additional validation
    return load_yaml(rules_file)


def check_rules(bom, config, rules, branch_name=None):
    """Apply governance rules. Returns list of errors."""
    errors = []

    source = bom.get('source_server', '')
    target = bom.get('target_server', '')

    # Get env types from servers
    servers = config.get('servers', {})
    source_env = servers.get(source, {}).get('env_type', '')
    target_env = servers.get(target, {}).get('env_type', '')

    # RULE 1: Prohibited deployment paths
    rule = rules.get('prohibited_deployment_paths', {})
    if rule.get('enabled'):
        paths = rule.get('paths', [])
        for path in paths:
            source_match = source_env == path['source']
            target_match = target_env in path['target']
            if source_match and target_match:
                reason = path.get('reason', 'Deployment path not allowed')
                errors.append(f"{reason} ({source_env} → {target_env})")
                break

    # RULE 2: Prod needs rollback
    rule = rules.get('require_prod_rollback', {})
    if rule.get('enabled'):
        applies_to = rule.get('applies_to', ['prod'])
        if target_env in applies_to and 'rollback_artifact' not in bom:
            errors.append(rule.get('message', 'Rollback artifact required'))

    # RULE 3: Prod needs change request
    rule = rules.get('require_prod_change_request', {})
    if rule.get('enabled'):
        applies_to = rule.get('applies_to', ['prod'])
        if target_env in applies_to and 'change_request' not in bom:
            errors.append(rule.get('message', 'Change request required'))

    # RULE 4: Source != target
    rule = rules.get('prevent_same_server', {})
    if rule.get('enabled'):
        if source and target and source == target:
            errors.append(rule.get('message', 'Source and target must differ'))

    # RULE 5: Functional BOMs need entities
    rule = rules.get('require_entities_functional', {})
    if rule.get('enabled'):
        profile = bom.get('profile', '')
        is_functional = 'functional' in profile
        is_rollback = 'rollback_artifact' in bom and 'entities' not in bom

        if is_functional and not is_rollback:
            entities = bom.get('entities', [])
            if not entities or len(entities) == 0:
                errors.append(rule.get('message', 'Entities required'))

    # RULE 6: Branch-environment alignment
    rule = rules.get('require_branch_environment_match', {})
    if rule.get('enabled') and branch_name:
        mappings = rule.get('mappings', {})

        # Determine branch type
        branch_type = None
        if branch_name.startswith('feature/'):
            branch_type = 'feature'
        elif branch_name == 'develop':
            branch_type = 'develop'
        elif branch_name == 'main':
            branch_type = 'main'

        if branch_type and branch_type in mappings:
            allowed_envs = mappings[branch_type].get('allowed_env_types', [])

            if target_env not in allowed_envs:
                message = rule.get('message', 'Environment mismatch')
                errors.append(
                    f"{message}\n"
                    f"    Branch: {branch_name} (allows: {', '.join(allowed_envs)})\n"
                    f"    BOM target_server: {target} (env_type: {target_env})"
                )

    return errors


def validate_semantic_version(version):
    """Validate semantic versioning format (e.g., 1.0.0)."""
    pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$'
    return re.match(pattern, version) is not None


def validate_bom(bom_file, branch_name=None):
    """
    Validate a single BOM file.

    Args:
        bom_file: Path to BOM file
        branch_name: Git branch name (for environment validation)

    Returns (is_valid, errors[])
    """
    errors = []
    bom_path = Path(bom_file)

    # Check file exists
    if not bom_path.exists():
        return False, [f"File not found: {bom_file}"]

    # Load YAML
    bom = load_yaml(bom_path)
    if isinstance(bom, tuple):  # Error occurred
        return False, [f"YAML syntax error: {bom[1]}"]

    # Check if BOM is empty
    if not bom:
        return False, ["BOM file is empty"]

    # Determine if this is a rollback BOM
    is_rollback = 'rollback_artifact' in bom and 'entities' not in bom

    # Common required fields
    required_common = ['version', 'profile', 'target_server']

    for field in required_common:
        if field not in bom:
            errors.append(f"Missing required field: {field}")

    # Check version format
    if 'version' in bom:
        if not validate_semantic_version(bom['version']):
            errors.append(f"Invalid version format: {bom['version']} (expected: X.Y.Z)")

    # Check profile exists
    if 'profile' in bom:
        root = Path(__file__).parent.parent
        profile_path = root / 'profiles' / f"{bom['profile']}.yaml"
        if not profile_path.exists():
            errors.append(f"Profile not found: {bom['profile']} (expected: {profile_path})")

    # Additional validation for non-rollback BOMs
    if not is_rollback:
        # Check source_server
        if 'source_server' not in bom:
            errors.append("Missing required field: source_server")

        # Check for functional vs baseline
        is_baseline = 'baseline' in bom.get('profile', '')

        if is_baseline:
            # Baseline BOM validation
            baseline_required = ['description', 'created_by']
            for field in baseline_required:
                if field not in bom:
                    errors.append(f"Missing required field for baseline: {field}")
        else:
            # Functional BOM validation
            functional_required = ['change_request', 'entities']
            for field in functional_required:
                if field not in bom:
                    errors.append(f"Missing required field for functional: {field}")

            # Check entities list
            if 'entities' in bom:
                if not isinstance(bom['entities'], list) or len(bom['entities']) == 0:
                    errors.append("Entities must be a non-empty list")
                else:
                    # Validate each entity
                    for i, entity in enumerate(bom['entities']):
                        if 'entity_id' not in entity:
                            errors.append(f"Entity {i}: missing entity_id")
                        if 'reference_code' not in entity:
                            errors.append(f"Entity {i}: missing reference_code")

    # Rollback BOM specific validation
    if is_rollback:
        if 'rollback_artifact' not in bom:
            errors.append("Rollback BOM must specify rollback_artifact")
        if 'description' not in bom:
            errors.append("Rollback BOM should include description")

    # Apply governance rules
    config = load_config()
    rules = load_rules()
    if config and rules:
        errors.extend(check_rules(bom, config, rules, branch_name))

    return len(errors) == 0, errors


def find_changed_bom_files():
    """
    Find BOM files that have changed in this commit.
    Uses git diff in CI, falls back to all BOMs locally.
    """
    root = Path(__file__).parent.parent
    bom_dir = root / 'boms'

    if not bom_dir.exists():
        return []

    # In CI, use git diff to find actually changed files
    commit_before = os.environ.get('CI_COMMIT_BEFORE_SHA')
    if commit_before:
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', f'{commit_before}...HEAD'],
                capture_output=True,
                text=True,
                check=True,
                cwd=root
            )
            changed_files = result.stdout.strip().split('\n')

            # Filter for only baseline.yaml and functional.yaml
            bom_files = []
            for file in changed_files:
                if file in ['boms/baseline.yaml', 'boms/functional.yaml']:
                    bom_files.append(root / file)

            return bom_files
        except subprocess.CalledProcessError:
            pass  # Fall through to local mode

    # Local mode: return all BOMs
    bom_files = []
    for yaml_file in bom_dir.rglob('*.yaml'):
        if 'test' not in yaml_file.parts:
            bom_files.append(yaml_file)

    return bom_files


def main():
    """Main validation entry point."""
    parser = argparse.ArgumentParser(description='Validate BOM files')
    parser.add_argument('--changed-files', action='store_true',
                        help='Validate only changed BOM files')
    parser.add_argument('--file', help='Validate specific BOM file')
    parser.add_argument('--branch', help='Git branch name (for environment validation)')

    args = parser.parse_args()

    # Determine which files to validate
    if args.file:
        bom_files = [Path(args.file)]
    elif args.changed_files:
        bom_files = find_changed_bom_files()
    else:
        print("Error: Specify --changed-files or --file")
        sys.exit(1)

    if not bom_files:
        print("No BOM files to validate")
        return

    # Extract branch name from argument or environment
    branch_name = args.branch or os.environ.get('CI_COMMIT_BRANCH')

    print("=" * 60)
    print("BOM VALIDATION")
    print("=" * 60)
    if branch_name:
        print(f"Branch: {branch_name}")
    print()

    # Check if both BOMs changed (fail fast)
    bom_names = [str(f.name) for f in bom_files]
    if 'baseline.yaml' in bom_names and 'functional.yaml' in bom_names:
        rules = load_rules()
        rule = rules.get('prevent_multiple_bom_changes', {})
        if rule.get('enabled'):
            print("✗ MULTIPLE BOM CHANGES DETECTED")
            print(f"  {rule.get('message')}")
            print("  Baseline and functional are different deployment types.")
            print("  Create separate commits for each.")
            print()
            print("=" * 60)
            print("VALIDATION FAILED")
            print("=" * 60)
            sys.exit(1)

    total_files = len(bom_files)
    valid_files = 0
    invalid_files = 0

    for bom_file in bom_files:
        print(f"Validating: {bom_file}")

        is_valid, errors = validate_bom(bom_file, branch_name)

        if is_valid:
            print("  ✓ Valid")
            valid_files += 1
        else:
            print("  ✗ Invalid")
            for error in errors:
                print(f"    - {error}")
            invalid_files += 1
        print()

    # Summary
    print("=" * 60)
    print(f"VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total files:   {total_files}")
    print(f"Valid:         {valid_files}")
    print(f"Invalid:       {invalid_files}")
    print()

    if invalid_files > 0:
        print(" Validation FAILED")
        sys.exit(1)
    else:
        print(" Validation PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
