#!/usr/bin/env python3
"""
Deployment utilities - shared helper functions.
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path

from ..config.validation import validate_bom


def load_yaml(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def deep_merge(base, override):
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
    root = Path(__file__).parent.parent.parent
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
    Path(output_path).parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False)
    print(f"Saved metadata: {output_path}")


def load_deployment_metadata(metadata_path="bundles/deployment-metadata.yaml"):
    if not Path(metadata_path).exists():
        print(f"Error: Metadata file not found: {metadata_path}")
        sys.exit(1)
    return load_yaml(metadata_path)


def get_flag_string(profile_name):
    """
    Get compiled flag string from profile.
    Calls flag compiler module and returns the 25-character Y/N string.
    """
    result = subprocess.run(
        ['python3', '-m', 'tools.config.flags', profile_name],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def apply_default_credentials(server_config, config):
    default_creds = config.get('default_credentials', {})

    # Ensure ssh_env_vars section exists
    if 'ssh_env_vars' not in server_config:
        server_config['ssh_env_vars'] = {}

    # Ensure ppm_api_env_vars section exists
    if 'ppm_api_env_vars' not in server_config:
        server_config['ppm_api_env_vars'] = {}

    ssh_vars = server_config['ssh_env_vars']
    ppm_vars = server_config['ppm_api_env_vars']

    # Apply SSH credential defaults (for remote server access)
    if 'username' not in ssh_vars and 'ssh_username' in default_creds:
        ssh_vars['username'] = default_creds['ssh_username']

    if 'password' not in ssh_vars and 'ssh_password' in default_creds:
        ssh_vars['password'] = default_creds['ssh_password']

    # Apply PPM/kMigrator credential defaults (for PPM API access)
    if 'username' not in ppm_vars and 'ppm_username' in default_creds:
        ppm_vars['username'] = default_creds['ppm_username']

    if 'password' not in ppm_vars and 'ppm_password' in default_creds:
        ppm_vars['password'] = default_creds['ppm_password']

    return server_config


def get_ppm_credentials(server_config=None):
    """Get PPM API credentials from environment (not SSH credentials)."""
    if not server_config:
        print("ERROR: server_config required for get_ppm_credentials()")
        sys.exit(1)

    ppm_vars = server_config.get('ppm_api_env_vars', {})
    username_env = ppm_vars.get('username')
    password_env = ppm_vars.get('password')

    if not username_env or not password_env:
        print(f"ERROR: Missing ppm_api_env_vars in server config")
        print(f"Add to deployment-config.yaml: ppm_api_env_vars: {{username: 'ENV_VAR', password: 'ENV_VAR'}}")
        sys.exit(1)

    username = os.environ.get(username_env)
    password = os.environ.get(password_env)

    if not username or not password:
        print(f"ERROR: Credentials not set: {username_env}, {password_env}")
        print(f"Set with: export {username_env}='user' {password_env}='pass'")
        sys.exit(1)

    print(f"[OK] PPM credentials loaded (user={username[:3]}...{username[-2:]})")
    return username, password


def is_remote_mode(server_config, config):
    """Check if we're using remote execution + storage backend."""
    return (
        server_config.get('ssh_host') is not None and
        config['deployment'].get('storage_backend', 'local') != 'local'
    )


def validate_bom_before_action(bom_file):
    """Helper to run validation and exit on failure."""
    print("\n=== VALIDATING BOM ===")
    is_valid, errors = validate_bom(bom_file)
    if not is_valid:
        print("BOM validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("[OK] BOM validation successful\n")


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
