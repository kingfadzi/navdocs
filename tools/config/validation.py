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
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def load_config():
    """Load deployment config and handle errors."""
    root = Path(__file__).parent.parent.parent
    config_file = root / 'config' / 'deployment-config.yaml'
    config, err = load_yaml(config_file)
    if err:
        print(f"Error loading deployment-config.yaml: {err}")
        sys.exit(1)
    return config


def load_rules():
    """Load governance rules and handle errors."""
    root = Path(__file__).parent.parent.parent
    rules_file = root / 'config' / 'rules.yaml'
    if not rules_file.exists():
        return {}  # No rules file is a valid state
    rules, err = load_yaml(rules_file)
    if err:
        print(f"Error loading rules.yaml: {err}")
        sys.exit(1)
    return rules


def _get_branch_type(branch_name):
    """Determine branch type from branch name."""
    if not branch_name:
        return None
    if branch_name.startswith('feature/'):
        return 'feature'
    if branch_name == 'develop':
        return 'develop'
    if branch_name == 'main':
        return 'main'
    return None


def check_rules(bom, config, rules, branch_name=None):
    """Apply governance rules. Returns list of errors."""
    errors = []

    source = bom.get('source_server', '')
    target = bom.get('target_server', '')

    servers = config.get('servers', {})
    source_env = servers.get(source, {}).get('env_type', '')
    target_env = servers.get(target, {}).get('env_type', '')

    # RULE 1: Sequential deployment promotion order (strict - no skipping)
    rule = rules.get('deployment_promotion_order', {})
    if rule.get('enabled'):
        sequence = rule.get('sequence', [])
        if source_env in sequence and target_env in sequence:
            source_idx = sequence.index(source_env)
            target_idx = sequence.index(target_env)
            if target_idx != source_idx + 1:
                if target_idx <= source_idx:
                    errors.append(f"{rule.get('message', 'Invalid deployment order')} ({source_env} to {target_env})")
                else:
                    expected_next = sequence[source_idx + 1]
                    errors.append(f"{rule.get('message', 'Invalid deployment order')} - Must deploy to {expected_next} next ({source_env} to {target_env})")

    # RULE 2: Prod needs rollback
    rule = rules.get('require_prod_rollback', {})
    if rule.get('enabled'):
        applies_to = rule.get('applies_to', ['prod'])
        if target_env in applies_to and 'rollback_pipeline_id' not in bom:
            errors.append(rule.get('message', 'Rollback pipeline ID required'))

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

    # RULE 5: Branch-environment alignment
    rule = rules.get('require_branch_environment_match', {})
    if rule.get('enabled') and branch_name:
        branch_type = _get_branch_type(branch_name)
        mappings = rule.get('mappings', {})

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


def validate_bom(bom_file, branch_name=None):
    """
    Validate a single BOM file (baseline.yaml or functional.yaml).
    """
    errors = []
    bom_path = Path(bom_file)

    if not bom_path.exists():
        return False, [f"File not found: {bom_file}"]

    bom, err = load_yaml(bom_path)
    if err:
        return False, [f"YAML syntax error: {err}"]

    if not bom:
        return False, ["BOM file is empty"]

    # Required fields for all BOMs
    required_fields = ['version', 'profile', 'source_server', 'target_server', 'created_by']
    for field in required_fields:
        if field not in bom:
            errors.append(f"Missing required field: {field}")

    # Check if profile file exists
    if 'profile' in bom:
        root = Path(__file__).parent.parent.parent
        profile_path = root / 'profiles' / f"{bom['profile']}.yaml"
        if not profile_path.exists():
            errors.append(f"Profile not found: {bom['profile']} (expected: {profile_path})")

    # Determine BOM type from profile and validate accordingly
    profile = bom.get('profile', '')
    is_rollback = 'rollback_pipeline_id' in bom

    if 'baseline' in profile.lower():
        # Baseline-specific validation
        if 'description' not in bom:
            errors.append("Baseline BOMs require 'description' field")
    elif 'functional' in profile.lower():
        # Functional-specific validation
        if not is_rollback and 'entities' not in bom:
            errors.append("Functional BOMs require 'entities' field (unless rollback)")
        if 'entities' in bom:
            if not isinstance(bom['entities'], list) or len(bom['entities']) == 0:
                errors.append("Entities must be a non-empty list")
            else:
                for i, entity in enumerate(bom['entities']):
                    if 'entity_id' not in entity:
                        errors.append(f"Entity {i}: missing entity_id")
                    if 'reference_code' not in entity:
                        errors.append(f"Entity {i}: missing reference_code")

    # Apply governance rules
    config = load_config()
    rules = load_rules()
    if config and rules:
        errors.extend(check_rules(bom, config, rules, branch_name))

    return len(errors) == 0, errors


def main():
    """Main validation entry point."""
    parser = argparse.ArgumentParser(description='Validate BOM files')
    parser.add_argument('--file', required=True, help='Validate specific BOM file')
    parser.add_argument('--branch', help='Git branch name (for environment validation)')

    args = parser.parse_args()

    bom_file = Path(args.file)
    branch_name = args.branch or os.environ.get('CI_COMMIT_BRANCH')

    print(f"\n=== BOM VALIDATION ===")
    print(f"File: {bom_file}")
    if branch_name:
        print(f"Branch: {branch_name}")
    print()

    is_valid, errors = validate_bom(bom_file, branch_name)

    if is_valid:
        print("[OK] Valid")
    else:
        print("✗ Invalid")
        for error in errors:
            print(f"  - {error}")

    print(f"\n=== RESULT: {'PASSED' if is_valid else f'FAILED ({len(errors)} errors)'} ===\n")
    sys.exit(0 if is_valid else 1)


if __name__ == '__main__':
    main()
