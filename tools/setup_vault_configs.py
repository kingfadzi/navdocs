#!/usr/bin/env python3
"""
Setup Vault Configurations for GitLab CI
Reads BOM file and outputs the appropriate Vault configs for the deployment.
"""

import sys
import yaml
from pathlib import Path


def load_yaml(file_path):
    """Load YAML file and return contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def get_vault_config(server_name, config):
    """Get vault configuration for a server."""
    if server_name not in config['servers']:
        print(f"Error: Server '{server_name}' not found in configuration", file=sys.stderr)
        sys.exit(1)

    server_config = config['servers'][server_name]

    if 'ci_vault_configs' not in server_config:
        print(f"Error: No ci_vault_configs defined for server '{server_name}'", file=sys.stderr)
        sys.exit(1)

    return server_config['ci_vault_configs']


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: setup_vault_configs.py <bom_file> <stage>", file=sys.stderr)
        print("  stage: extract, import, or archive", file=sys.stderr)
        sys.exit(1)

    bom_file = sys.argv[1]
    stage = sys.argv[2]

    if stage not in ['extract', 'import', 'archive']:
        print(f"Error: Invalid stage '{stage}'. Must be extract, import, or archive", file=sys.stderr)
        sys.exit(1)

    # Load BOM to determine source/target servers
    bom = load_yaml(bom_file)

    # Load deployment config
    root = Path(__file__).parent.parent
    config_path = root / "config" / "deployment-config.yaml"
    config = load_yaml(config_path)

    # Determine which server's credentials to use
    if stage == 'extract':
        # Extract needs SOURCE server credentials
        server_name = bom['source_server']
    else:
        # Import and Archive need TARGET server credentials
        server_name = bom['target_server']

    # Get and output the Vault configuration
    vault_config = get_vault_config(server_name, config)
    print(vault_config)


if __name__ == '__main__':
    main()
