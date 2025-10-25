#!/usr/bin/env python3
import yaml
import sys
import argparse

# This script generates a dynamic GitLab CI child pipeline by populating a template.
# Uses OpenText CSM vault component exclusively for secret management.

def load_yaml(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def generate_component_include(csm_config, anchor_name, vault_role_name, vault_secret_path):
    """Generate CSM vault component include with hardcoded CSM parameter names."""
    component_url = csm_config['component_url']
    component_version = csm_config['component_version']

    return f"""  - component: {component_url}@{component_version}
    inputs:
      anchor_name: '{anchor_name}'
      csm_role: '{vault_role_name}'
      csm_secret_urls: '["{vault_secret_path}"]'
"""

def generate_vault_references(vault_configs):
    """Generate !reference directives for vault component before_scripts."""
    references = ["    - !reference [.job_base, before_script]"]

    for vault_role, secret_path, anchor_name in vault_configs:
        references.append(f"    - !reference [.{anchor_name}, before_script]")

    return "\n".join(references)

def _add_vault_includes(vault_role_configs, csm_config):
    """Generate CSM vault component includes for multiple vault roles."""
    vault_includes = ""
    for role_config in vault_role_configs:
        role_name = role_config['name']
        secret_path = role_config['path']
        path_suffix = secret_path.split('/')[-1]
        anchor_name = f'vault-{role_name}-{path_suffix}'
        vault_includes += generate_component_include(csm_config, anchor_name, role_name, secret_path)
    return vault_includes


def generate_pipeline(bom_file_path, config_file_path, template_file_path):
    """Generates the child pipeline YAML by populating a template."""

    bom = load_yaml(bom_file_path)
    deployment_config = load_yaml(config_file_path)

    # Determine source and target server names
    source_server = bom.get('source_server')
    target_server = bom.get('target_server')
    source_server_name = source_server.get('name') if isinstance(source_server, dict) else source_server
    target_server_name = target_server.get('name') if isinstance(target_server, dict) else target_server

    if not source_server_name or not target_server_name:
        print("Error: BOM file must contain source_server.name and target_server.name", file=sys.stderr)
        sys.exit(1)

    # Get server configurations
    source_server_config = deployment_config['servers'][source_server_name]
    target_server_config = deployment_config['servers'][target_server_name]
    s3_config = deployment_config['s3']

    # Get CSM component configuration
    csm_config = deployment_config['csm']

    source_vault_roles = source_server_config['vault_roles']
    target_vault_roles = target_server_config['vault_roles']
    s3_vault_roles = s3_config['vault_roles']

    # Generate CSM vault component includes
    vault_includes = "# CSM vault component includes for dynamic child pipeline\ninclude:\n"
    vault_includes += _add_vault_includes(source_vault_roles, csm_config)
    vault_includes += _add_vault_includes(target_vault_roles, csm_config)
    vault_includes += _add_vault_includes(s3_vault_roles, csm_config)
    vault_includes += "\n"

    # --- Step 3: Generate Vault References for Each Job ---
    def build_vault_configs(vault_role_list):
        vault_configs = []
        for role_config in vault_role_list:
            role_name = role_config['name']
            secret_path = role_config['path']
            path_suffix = secret_path.split('/')[-1]
            anchor_name = f"vault-{role_name}-{path_suffix}"
            vault_configs.append((role_name, secret_path, anchor_name))
        return vault_configs

    # Extract job needs source server roles + S3 roles
    extract_vault_configs = build_vault_configs(source_vault_roles)
    extract_vault_configs.extend(build_vault_configs(s3_vault_roles))
    extract_vault_refs = generate_vault_references(extract_vault_configs)

    # Import job needs target server roles + S3 roles
    import_vault_configs = build_vault_configs(target_vault_roles)
    import_vault_configs.extend(build_vault_configs(s3_vault_roles))
    import_vault_refs = generate_vault_references(import_vault_configs)

    # Archive job needs target server roles + S3 roles
    archive_vault_configs = build_vault_configs(target_vault_roles)
    archive_vault_configs.extend(build_vault_configs(s3_vault_roles))
    archive_vault_refs = generate_vault_references(archive_vault_configs)

    # --- Step 4: Populate the Template ---
    with open(template_file_path, 'r') as template_file:
        template_content = template_file.read()

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
