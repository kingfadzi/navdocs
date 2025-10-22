#!/usr/bin/env python3
"""
Deployment utilities - shared helper functions.
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path

# Import validate_bom - handle both direct execution and package import
try:
    from validate_bom import validate_bom
except ImportError:
    from tools.validate_bom import validate_bom


def load_yaml(file_path):
    """Load YAML file and return contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def deep_merge(base, override):
    """Deep merge override dict into base dict."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config():
    """
    Load configuration with optional local overrides.
    - Default: deployment-config.yaml (production mode)
    - DEPLOYMENT_ENV=local: merges deployment-config.local.yaml overrides
    """
    root = Path(__file__).parent.parent
    base_path = root / "config" / "deployment-config.yaml"
    base_config = load_yaml(base_path)

    env = os.environ.get('DEPLOYMENT_ENV', '').strip()
    if env == 'local':
        override_path = root / "config" / "deployment-config.local.yaml"
        if override_path.exists():
            override_config = load_yaml(override_path)
            return deep_merge(base_config, override_config)

    return base_config


def save_deployment_metadata(metadata, output_path="bundles/deployment-metadata.yaml"):
    """Save deployment state for passing between pipeline stages."""
    Path(output_path).parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False)
    print(f"Saved metadata: {output_path}")


def load_deployment_metadata(metadata_path="bundles/deployment-metadata.yaml"):
    """Load deployment state from previous pipeline stage."""
    if not Path(metadata_path).exists():
        print(f"Error: Metadata file not found: {metadata_path}")
        sys.exit(1)
    return load_yaml(metadata_path)


def get_flag_string(profile_name):
    """
    Get compiled flag string from profile.
    Calls flag_compiler.py and returns the 25-character Y/N string.
    """
    script_dir = Path(__file__).parent
    compiler = script_dir / "flag_compiler.py"
    result = subprocess.run(
        ['python3', str(compiler), profile_name],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def get_credentials():
    """
    Get PPM service account credentials from environment.
    Returns tuple (username, password) or exits if not found.
    """
    username = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
    password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')

    if not username or not password:
        print("ERROR: PPM credentials not set")
        print("  Required: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD")
        sys.exit(1)

    print(f"✓ Credentials loaded (user={username[:3]}...{username[-2:]}, password={'*' * len(password)})")
    return username, password


def is_remote_mode(server_config, config):
    """Check if we're using remote execution + storage backend."""
    return (
        server_config.get('ssh_host') is not None and
        config['deployment'].get('storage_backend', 'local') != 'local'
    )


def validate_bom_before_action(bom_file):
    """Helper to run validation and exit on failure."""
    print("=" * 60)
    print("VALIDATING BOM")
    print("=" * 60)
    is_valid, errors = validate_bom(bom_file)
    if not is_valid:
        print("BOM validation failed. Errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease fix the errors in the BOM file before proceeding.")
        sys.exit(1)
    print("BOM validation successful.")
    print("=" * 60)
    print()


def get_vault_config_command(server_name):
    """Extract CI Vault configuration for a server."""
    config = load_config()

    if server_name not in config['servers']:
        print(f"Error: Server '{server_name}' not found in configuration", file=sys.stderr)
        sys.exit(1)

    server_config = config['servers'][server_name]

    if 'ci_vault_configs' not in server_config:
        print(f"Error: No ci_vault_configs defined for server '{server_name}'", file=sys.stderr)
        sys.exit(1)

    # Print raw string value (no modification)
    print(server_config['ci_vault_configs'])
