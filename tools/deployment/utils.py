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
    from config.validation import validate_bom
except ImportError:
    from tools.config.validation import validate_bom


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
    Calls flag compiler module and returns the 25-character Y/N string.
    """
    result = subprocess.run(
        ['python3', '-m', 'tools.config.flags', profile_name],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def apply_default_credentials(server_config, config):
    """
    Apply default credentials to server config if not already present.

    Args:
        server_config: Server configuration dict
        config: Full deployment configuration dict

    Returns:
        Server config with credential env vars populated (in-place modification)
    """
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
    """
    Get PPM/kMigrator service account credentials from environment.
    These credentials are used for PPM API authentication (not SSH).

    Args:
        server_config: Server configuration dict with ppm_api_env_vars section.
                      NO DEFAULTS - configuration must be explicit.

    Returns:
        Tuple of (username, password) or exits if not found.
    """
    # Require explicit configuration - NO implicit defaults
    if not server_config:
        print("ERROR: server_config must be provided to get_ppm_credentials()")
        sys.exit(1)

    ppm_vars = server_config.get('ppm_api_env_vars', {})
    username_env = ppm_vars.get('username')
    password_env = ppm_vars.get('password')

    # Fail fast if credential env vars are not configured
    if not username_env or not password_env:
        print("=" * 60)
        print("ERROR: PPM credential environment variable names not configured")
        print("=" * 60)
        print("\nRequired in server config:")
        print("  ppm_api_env_vars:")
        print("    username: 'PPM_SERVICE_ACCOUNT_USER'")
        print("    password: 'PPM_SERVICE_ACCOUNT_PASSWORD'")
        print("\nAdd to config/deployment-config.yaml:")
        print("  servers:")
        print("    your-server:")
        print("      ppm_api_env_vars:")
        print("        username: 'PPM_SERVICE_ACCOUNT_USER'")
        print("        password: 'PPM_SERVICE_ACCOUNT_PASSWORD'")
        print("=" * 60)
        sys.exit(1)

    # Read credentials from configured env vars
    username = os.environ.get(username_env)
    password = os.environ.get(password_env)

    if not username or not password:
        print("=" * 60)
        print("ERROR: PPM credentials not set in environment")
        print("=" * 60)
        print(f"\nRequired environment variables:")
        print(f"  {username_env}")
        print(f"  {password_env}")
        print(f"\nSet them with:")
        print(f"  export {username_env}='your_ppm_username'")
        print(f"  export {password_env}='your_ppm_password'")
        print(f"\nOr add to ~/.bashrc or create a credentials file:")
        print(f"  echo 'export {username_env}=your_username' >> ~/.ppm_credentials")
        print(f"  echo 'export {password_env}=your_password' >> ~/.ppm_credentials")
        print(f"  source ~/.ppm_credentials")
        print("=" * 60)
        sys.exit(1)

    print(f"✓ PPM credentials loaded (user={username[:3]}...{username[-2:]}, password={'*' * len(password)})")
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
