#!/usr/bin/env python3
import yaml
import sys
import argparse

# This script generates a dynamic GitLab CI child pipeline by populating a template.

def load_yaml(file_path):
    """Loads a YAML file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def get_vault_provider(server_or_s3_config, deployment_config):
    """
    Get the vault component provider for a server or S3 configuration.

    Args:
        server_or_s3_config: Server config dict or S3 config dict
        deployment_config: Full deployment configuration

    Returns:
        Provider configuration dict with component_url, component_version, parameter_mappings
    """
    # Check for provider override in server/s3 config
    provider_name = server_or_s3_config.get('vault_component_provider')

    # Fall back to global default
    if not provider_name:
        provider_name = deployment_config.get('vault_component_provider', 'standard')

    # Get provider config
    providers = deployment_config.get('vault_component_providers', {})
    if provider_name not in providers:
        print(f"Error: Vault component provider '{provider_name}' not found in vault_component_providers", file=sys.stderr)
        print(f"Available providers: {list(providers.keys())}", file=sys.stderr)
        sys.exit(1)

    return providers[provider_name]


def generate_component_include(provider, anchor_name, role, secret_paths):
    """
    Generate a single vault component include using provider configuration.

    Args:
        provider: Provider config dict with component_url, component_version, parameter_mappings
        anchor_name: Anchor name for the component (e.g., 'vault-ppm-dev')
        role: Vault role name
        secret_paths: Vault secret path

    Returns:
        YAML-formatted component include string
    """
    component_url = provider['component_url']
    component_version = provider['component_version']
    param_mappings = provider['parameter_mappings']

    # Map our internal parameter names to provider's parameter names
    anchor_param = param_mappings['anchor_name']
    role_param = param_mappings['role']
    paths_param = param_mappings['secret_paths']

    return f"""  - component: {component_url}@{component_version}
    inputs:
      {anchor_param}: '{anchor_name}'
      {role_param}: '{role}'
      {paths_param}: '["{secret_paths}"]'
"""

def generate_vault_references(vault_configs):
    """
    Generate !reference directives for vault component before_scripts.
    The component is pre-configured with the necessary VAULT_ROLE and VAULT_SECRET_PATHS
    via its inputs, so we only need to reference its script.

    Args:
        vault_configs: List of tuples (role, path, anchor_name)
                      e.g., [('ppm-dev', 'secret/data/ppm/dev/useast', 'vault-ppm-dev'),
                             ('s3-read', 'secret/data/shared/s3', 'vault-s3')]

    Returns:
        YAML-formatted string with !reference directives
    """
    refs = ["    - !reference [.job_base, before_script]"]

    for role, path, anchor in vault_configs:
        # The component is already configured with the correct role and path via its inputs.
        # We only need to reference its before_script.
        refs.append(f"    - !reference [.{anchor}, before_script]")

    return "\n".join(refs)

def generate_pipeline(bom_file_path, config_file_path, template_file_path):
    """Generates the child pipeline YAML by populating a template."""

    bom = load_yaml(bom_file_path)
    deployment_config = load_yaml(config_file_path)

    # --- Step 1: Determine Source and Target Roles (The Logic) ---
    source_server = bom.get('source_server')
    target_server = bom.get('target_server')

    # Handle both string and dict formats for server names
    source_server_name = source_server.get('name') if isinstance(source_server, dict) else source_server
    target_server_name = target_server.get('name') if isinstance(target_server, dict) else target_server

    if not source_server_name or not target_server_name:
        print("Error: BOM file must contain source_server.name and target_server.name", file=sys.stderr)
        sys.exit(1)

    # Find the roles and paths from the deployment config
    source_server_config = deployment_config['servers'][source_server_name]
    target_server_config = deployment_config['servers'][target_server_name]
    s3_config = deployment_config['s3']

    source_role = source_server_config['vault_roles'][0]['name']
    source_path = source_server_config['vault_roles'][0]['path']
    target_role = target_server_config['vault_roles'][0]['name']
    target_path = target_server_config['vault_roles'][0]['path']
    s3_role = s3_config['vault_roles'][0]['name']
    s3_path = s3_config['vault_roles'][0]['path']

    # --- Step 2: Generate Vault Component Includes (Pluggable Providers) ---
    # Get vault providers for each component
    source_provider = get_vault_provider(source_server_config, deployment_config)
    target_provider = get_vault_provider(target_server_config, deployment_config)
    s3_provider = get_vault_provider(s3_config, deployment_config)

    # Generate component includes using provider configurations
    vault_includes = "# Vault component includes for dynamic child pipeline\ninclude:\n"
    vault_includes += generate_component_include(source_provider, f'vault-{source_role}', source_role, source_path)
    vault_includes += generate_component_include(target_provider, f'vault-{target_role}', target_role, target_path)
    vault_includes += generate_component_include(s3_provider, 'vault-s3', s3_role, s3_path)
    vault_includes += "\n"

    # --- Step 3: Generate Vault References for Each Job ---
    # Extract job needs source PPM role + S3
    extract_vault_refs = generate_vault_references([
        (source_role, source_path, f'vault-{source_role}'),
        (s3_role, s3_path, 'vault-s3')
    ])

    # Import job needs target PPM role + S3
    import_vault_refs = generate_vault_references([
        (target_role, target_path, f'vault-{target_role}'),
        (s3_role, s3_path, 'vault-s3')
    ])

    # Archive job needs target PPM role + S3
    archive_vault_refs = generate_vault_references([
        (target_role, target_path, f'vault-{target_role}'),
        (s3_role, s3_path, 'vault-s3')
    ])

    # --- Step 4: Populate the Template ---
    with open(template_file_path, 'r') as f:
        template_content = f.read()

    # Replace vault reference placeholders
    pipeline_content = template_content.replace('%%EXTRACT_VAULT_REFS%%', extract_vault_refs)
    pipeline_content = pipeline_content.replace('%%IMPORT_VAULT_REFS%%', import_vault_refs)
    pipeline_content = pipeline_content.replace('%%ARCHIVE_VAULT_REFS%%', archive_vault_refs)

    # --- Step 5: Output the final YAML with includes prepended ---
    print(vault_includes + pipeline_content)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate GitLab CI child pipeline for PPM deployment.")
    parser.add_argument('--bom', required=True, help="Path to the BOM file.")
    parser.add_argument('--config', default='config/deployment-config.yaml', help="Path to the deployment config file.")
    parser.add_argument('--template', default='templates/child-pipeline-template.yml', help="Path to the child pipeline template.")
    args = parser.parse_args()
    
    generate_pipeline(args.bom, args.config, args.template)
