#!/usr/bin/env python3
import yaml
import sys
import argparse

# This script generates a dynamic GitLab CI child pipeline by populating a template.

def load_yaml(file_path):
    """Loads a YAML file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def generate_vault_references(roles):
    """
    Generate !reference directives for vault component before_scripts.

    Args:
        roles: List of vault role names (e.g., ['ppm-dev', 's3'])

    Returns:
        YAML-formatted string with !reference directives
    """
    refs = ["    - !reference [.job_base, before_script]"]
    for role in roles:
        refs.append(f"    - !reference [.vault-{role}, before_script]")
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
    source_role = deployment_config['servers'][source_server_name]['vault_roles'][0]['name']
    source_path = deployment_config['servers'][source_server_name]['vault_roles'][0]['path']
    target_role = deployment_config['servers'][target_server_name]['vault_roles'][0]['name']
    target_path = deployment_config['servers'][target_server_name]['vault_roles'][0]['path']
    s3_role = deployment_config['s3']['vault_roles'][0]['name']
    s3_path = deployment_config['s3']['vault_roles'][0]['path']

    # --- Step 2: Generate Vault Component Includes ---
    vault_includes = f"""# Vault component includes for dynamic child pipeline
include:
  - component: eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@v1.0.1
    inputs:
      anchor_name: 'vault-{source_role}'
      vault_role: '{source_role}'
      vault_secret_paths: '["{source_path}"]'
  - component: eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@v1.0.1
    inputs:
      anchor_name: 'vault-{target_role}'
      vault_role: '{target_role}'
      vault_secret_paths: '["{target_path}"]'
  - component: eros.butterflycluster.com/staging/vault-secret-fetcher/vault-retrieve@v1.0.1
    inputs:
      anchor_name: 'vault-s3'
      vault_role: '{s3_role}'
      vault_secret_paths: '["{s3_path}"]'

"""

    # --- Step 3: Generate Vault References for Each Job ---
    # Extract job needs source PPM role + S3
    extract_vault_refs = generate_vault_references([source_role, 's3'])

    # Import job needs target PPM role + S3
    import_vault_refs = generate_vault_references([target_role, 's3'])

    # Archive job needs target PPM role + S3
    archive_vault_refs = generate_vault_references([target_role, 's3'])

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
