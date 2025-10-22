#!/usr/bin/env python3
"""
PPM Flag Compiler
Converts profile flags (YAML) to kMigrator flag string (YYYYYNNNN...)

# Reference: OpenText PPM kMigratorImport.sh Flag Definitions
# https://admhelp.microfocus.com/ppm/en/25.1-25.3/Help/Content/SA/InstallAdmin/122150_InstallAdmin_Server.htm
#
# These 25 flags control how entities are imported:
# - Flags 1-9, 13-25: Replace existing entities (Y/N)
# - Flags 10-12: Add missing dependencies (Y/N)

"""

import yaml
import sys
from pathlib import Path


def load_yaml(file_path):
    """Load YAML file and return contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def validate_flag_dependencies(profile_flags):
    """
    Validate flag dependencies according to PPM documentation.

    Returns: (is_valid, error_messages)
    """
    errors = []

    # Rule 1: Flag 22 (replace_portfolio_type) requires Flag 16 (replace_module)
    if profile_flags.get('replace_portfolio_type', False):
        if not profile_flags.get('replace_module', False):
            errors.append(
                "Flag 22 (replace_portfolio_type) requires Flag 16 (replace_module) to be enabled.\n"
                "    Documentation: If you want to replace the existing portfolio type, you should also\n"
                "    replace the existing module (set the Flag 16 to Y)."
            )

    # Rule 2: Flag 25 (replace_chatbot_intents) requires Flag 7 (replace_report_type)
    if profile_flags.get('replace_chatbot_intents', False):
        if not profile_flags.get('replace_report_type', False):
            errors.append(
                "Flag 25 (replace_chatbot_intents) requires Flag 7 (replace_report_type) to be enabled.\n"
                "    Documentation: If you want to replace existing Chatbot intents, you should also\n"
                "    replace the existing report type (set the Flag 7 to Y)."
            )

    return len(errors) == 0, errors


def build_flag_string(profile_flags, flag_schema):
    """
    Build 25-character Y/N string from profile flags.

    Example:
      profile_flags = {'replace_workflow': True, 'add_missing_environment': False, ...}
      flag_schema = list of flag definitions with position and key
      returns: "YYYYYNNNNYYYYYNNNNNNNNN"
    """
    # Sort schema by position (1, 2, 3, ... 25)
    sorted_schema = sorted(flag_schema, key=lambda x: x['position'])

    # Build flag string character by character
    flag_string = ""
    for flag_def in sorted_schema:
        key = flag_def['key']
        is_enabled = profile_flags.get(key, False)

        # Flag 24 (replace_custom_menu) is special - always replaced regardless of Y/N
        # For consistency with other flags, we still output the user's value
        # but note that PPM ignores this flag

        # Add 'Y' if enabled, 'N' if not
        if is_enabled:
            flag_string += "Y"
        else:
            flag_string += "N"

    return flag_string


def main():
    """Main entry point - read profile and output flag string."""

    # Check command line
    if len(sys.argv) < 2:
        print("Usage: flag_compiler.py <profile_name>")
        print("Example: flag_compiler.py baseline")
        sys.exit(1)

    profile_name = sys.argv[1]

    # Get paths
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent

    schema_file = root_dir / "profiles" / "ppm-flag-schema.yaml"
    profile_file = root_dir / "profiles" / f"{profile_name}.yaml"

    # Load files
    schema = load_yaml(schema_file)
    profile = load_yaml(profile_file)

    # Validate flag dependencies
    is_valid, errors = validate_flag_dependencies(profile['flags'])
    if not is_valid:
        print(f"ERROR: Flag dependency validation failed for profile '{profile_name}':", file=sys.stderr)
        print("", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Please update the profile to fix these dependencies.", file=sys.stderr)
        sys.exit(1)

    # Build flag string
    flag_string = build_flag_string(profile['flags'], schema['flag_schema'])

    # Output just the flag string (for easy parsing by deploy.py)
    print(flag_string)


if __name__ == "__main__":
    main()
