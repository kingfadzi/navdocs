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

    # Get ALL vault roles for source and target servers (not just the first one)
    source_vault_roles = source_server_config['vault_roles']
    target_vault_roles = target_server_config['vault_roles']
    s3_vault_roles = s3_config['vault_roles']

    # --- Step 2: Generate Vault Component Includes (Pluggable Providers) ---
    # Get vault providers for each component
    source_provider = get_vault_provider(source_server_config, deployment_config)
    target_provider = get_vault_provider(target_server_config, deployment_config)
    s3_provider = get_vault_provider(s3_config, deployment_config)

    # Generate component includes using provider configurations
    vault_includes = "# Vault component includes for dynamic child pipeline\ninclude:\n"

    # Include ALL source server vault roles (SSH + PPM credentials)
    for role_config in source_vault_roles:
        role_name = role_config['name']
        role_path = role_config['path']
        # Extract unique identifier from path (e.g., "mars" from "secret/data/infrastructure/ssh/mars")
        path_suffix = role_path.split('/')[-1]
        unique_anchor = f'vault-{role_name}-{path_suffix}'
        vault_includes += generate_component_include(source_provider, unique_anchor, role_name, role_path)

    # Include ALL target server vault roles (SSH + PPM credentials)
    for role_config in target_vault_roles:
        role_name = role_config['name']
        role_path = role_config['path']
        # Extract unique identifier from path (e.g., "phobos" from "secret/data/infrastructure/ssh/phobos")
        path_suffix = role_path.split('/')[-1]
        unique_anchor = f'vault-{role_name}-{path_suffix}'
        vault_includes += generate_component_include(target_provider, unique_anchor, role_name, role_path)

    # Include S3 vault roles
    for role_config in s3_vault_roles:
        role_name = role_config['name']
        role_path = role_config['path']
        # Extract unique identifier from path (e.g., "s3" from "secret/data/shared/s3")
        path_suffix = role_path.split('/')[-1]
        unique_anchor = f'vault-{role_name}-{path_suffix}'
        vault_includes += generate_component_include(s3_provider, unique_anchor, role_name, role_path)

    vault_includes += "\n"

    # --- Step 3: Generate Vault References for Each Job ---
    # Extract job needs ALL source server roles + S3
    extract_vault_configs = [(r['name'], r['path'], f"vault-{r['name']}-{r['path'].split('/')[-1]}") for r in source_vault_roles]
    extract_vault_configs.extend([(r['name'], r['path'], f"vault-{r['name']}-{r['path'].split('/')[-1]}") for r in s3_vault_roles])
    extract_vault_refs = generate_vault_references(extract_vault_configs)

    # Import job needs ALL target server roles + S3
    import_vault_configs = [(r['name'], r['path'], f"vault-{r['name']}-{r['path'].split('/')[-1]}") for r in target_vault_roles]
    import_vault_configs.extend([(r['name'], r['path'], f"vault-{r['name']}-{r['path'].split('/')[-1]}") for r in s3_vault_roles])
    import_vault_refs = generate_vault_references(import_vault_configs)

    # Archive job needs ALL target server roles + S3
    archive_vault_configs = [(r['name'], r['path'], f"vault-{r['name']}-{r['path'].split('/')[-1]}") for r in target_vault_roles]
    archive_vault_configs.extend([(r['name'], r['path'], f"vault-{r['name']}-{r['path'].split('/')[-1]}") for r in s3_vault_roles])
    archive_vault_refs = generate_vault_references(archive_vault_configs)

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
