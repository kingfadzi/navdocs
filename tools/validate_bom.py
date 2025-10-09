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
    root = Path(__file__).parent.parent
    config_file = root / 'config' / 'deployment-config.yaml'
    config, err = load_yaml(config_file)
    if err:
        print(f"Error loading deployment-config.yaml: {err}")
        sys.exit(1)
    return config


def load_rules():
    """Load governance rules and handle errors."""
    root = Path(__file__).parent.parent
    rules_file = root / 'config' / 'rules.yaml'
    if not rules_file.exists():
        return {}  # No rules file is a valid state
    rules, err = load_yaml(rules_file)
    if err:
        print(f"Error loading rules.yaml: {err}")
        sys.exit(1)
    return rules


def check_rules(section, top_level_bom, config, rules, branch_name=None):
    """Apply governance rules. Returns list of errors."""
    errors = []

    source = top_level_bom.get('source_server', '')
    target = top_level_bom.get('target_server', '')

    # Get env types from servers
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
                    errors.append(f"{rule.get('message', 'Invalid deployment order')} ({source_env} → {target_env})")
                else:
                    expected_next = sequence[source_idx + 1]
                    errors.append(f"{rule.get('message', 'Invalid deployment order')} - Must deploy to {expected_next} next ({source_env} → {target_env})")

    # RULE 2: Prod needs rollback
    rule = rules.get('require_prod_rollback', {})
    if rule.get('enabled'):
        applies_to = rule.get('applies_to', ['prod'])
        if target_env in applies_to and 'rollback_pipeline_id' not in section:
            section_name = section.get('profile', 'section')
            errors.append(f"[{section_name}] {rule.get('message', 'Rollback pipeline ID required')}")

    # RULE 3: Prod needs change request
    rule = rules.get('require_prod_change_request', {})
    if rule.get('enabled'):
        applies_to = rule.get('applies_to', ['prod'])
        if target_env in applies_to and 'change_request' not in top_level_bom:
            errors.append(rule.get('message', 'Change request required'))

    # RULE 4: Source != target
    rule = rules.get('prevent_same_server', {})
    if rule.get('enabled'):
        if source and target and source == target:
            errors.append(rule.get('message', 'Source and target must differ'))

    # RULE 5: Branch-environment alignment
    rule = rules.get('require_branch_environment_match', {})
    if rule.get('enabled') and branch_name:
        mappings = rule.get('mappings', {})
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


def validate_bom_section(bom_section, section_name, top_level_bom, config, rules, branch_name):
    """
    Validate a single section (baseline or functional) of the BOM.
    Returns a list of errors.
    """
    errors = []
    is_rollback = 'rollback_pipeline_id' in bom_section

    # Common required fields
    if 'profile' not in bom_section:
        errors.append(f"[{section_name}] Missing required field: profile")

    # Check profile exists
    if 'profile' in bom_section:
        root = Path(__file__).parent.parent
        profile_path = root / 'profiles' / f"{bom_section['profile']}.yaml"
        if not profile_path.exists():
            errors.append(f"[{section_name}] Profile not found: {bom_section['profile']} (expected: {profile_path})")

    # Section-specific validation
    if section_name == 'baseline':
        if 'description' not in bom_section:
            errors.append(f"[{section_name}] Missing required field: description")
    elif section_name == 'functional':
        if not is_rollback and 'entities' not in bom_section:
            errors.append(f"[{section_name}] Missing required field: entities")
        if 'entities' in bom_section:
            if not isinstance(bom_section['entities'], list) or len(bom_section['entities']) == 0:
                errors.append(f"[{section_name}] Entities must be a non-empty list")
            else:
                for i, entity in enumerate(bom_section['entities']):
                    if 'entity_id' not in entity:
                        errors.append(f"[{section_name}] Entity {i}: missing entity_id")
                    if 'reference_code' not in entity:
                        errors.append(f"[{section_name}] Entity {i}: missing reference_code")

    # Apply governance rules
    if config and rules:
        errors.extend(check_rules(bom_section, top_level_bom, config, rules, branch_name))

    return errors


def validate_bom(bom_file, branch_name=None):
    """
    Validate the consolidated boms/deployment.yaml file.
    """
    errors = []
    bom_path = Path(bom_file)

    if not bom_path.exists():
        return False, [f"File not found: {bom_file}"]

    bom_content, err = load_yaml(bom_path)
    if err:
        return False, [f"YAML syntax error: {err}"]

    if not bom_content:
        return False, ["BOM file is empty"]

    # General required fields
    top_level_required = ['version', 'created_by', 'source_server', 'target_server']
    for field in top_level_required:
        if field not in bom_content:
            errors.append(f"Missing required top-level field: {field}")

    # Check which sections are present and enabled
    baseline_section = bom_content.get('baseline')
    functional_section = bom_content.get('functional')
    is_baseline_enabled = isinstance(baseline_section, dict) and baseline_section.get('enabled', False)
    is_functional_enabled = isinstance(functional_section, dict) and functional_section.get('enabled', False)

    if not is_baseline_enabled and not is_functional_enabled:
        errors.append("BOM must contain at least one enabled 'baseline' or 'functional' section.")

    config = load_config()
    rules = load_rules()

    if is_baseline_enabled:
        errors.extend(validate_bom_section(baseline_section, 'baseline', bom_content, config, rules, branch_name))

    if is_functional_enabled:
        errors.extend(validate_bom_section(functional_section, 'functional', bom_content, config, rules, branch_name))

    return len(errors) == 0, errors


def main():
    """Main validation entry point."""
    parser = argparse.ArgumentParser(description='Validate BOM files')
    parser.add_argument('--file', required=True, help='Validate specific BOM file')
    parser.add_argument('--branch', help='Git branch name (for environment validation)')

    args = parser.parse_args()

    bom_file = Path(args.file)
    branch_name = args.branch or os.environ.get('CI_COMMIT_BRANCH')

    print("=" * 60)
    print("BOM VALIDATION")
    print("=" * 60)
    print(f"File: {bom_file}")
    if branch_name:
        print(f"Branch: {branch_name}")
    print()

    is_valid, errors = validate_bom(bom_file, branch_name)

    if is_valid:
        print("  ✓ Valid")
    else:
        print("  ✗ Invalid")
        for error in errors:
            print(f"    - {error}")
    print()

    # Summary
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    if not is_valid:
        print(f"Result: FAILED ({len(errors)} errors)")
        sys.exit(1)
    else:
        print("Result: PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
