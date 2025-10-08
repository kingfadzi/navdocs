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

    schema_file = script_dir / "ppm-flag-schema.yaml"
    profile_file = root_dir / "profiles" / f"{profile_name}.yaml"

    # Load files
    schema = load_yaml(schema_file)
    profile = load_yaml(profile_file)

    # Build flag string
    flag_string = build_flag_string(profile['flags'], schema['flag_schema'])

    # Output just the flag string (for easy parsing by deploy.py)
    print(flag_string)


if __name__ == "__main__":
    main()
