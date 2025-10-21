#!/usr/bin/env python3
import yaml
import sys
import argparse

# This script generates a dynamic GitLab CI child pipeline by populating a template.

def load_yaml(file_path):
    """Loads a YAML file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

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

    # Find the roles from the deployment config
    source_role = deployment_config['servers'][source_server_name]['vault_roles'][0]['name']
    target_role = deployment_config['servers'][target_server_name]['vault_roles'][0]['name']

    # --- Step 2: Populate the Template (The Presentation) ---
    with open(template_file_path, 'r') as f:
        template_content = f.read()

    # Replace placeholders
    pipeline_content = template_content.replace('%%SOURCE_ROLE%%', source_role)
    pipeline_content = pipeline_content.replace('%%TARGET_ROLE%%', target_role)

    # --- Step 3: Output the final YAML ---
    print(pipeline_content)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate GitLab CI child pipeline for PPM deployment.")
    parser.add_argument('--bom', required=True, help="Path to the BOM file.")
    parser.add_argument('--config', default='config/deployment-config.yaml', help="Path to the deployment config file.")
    parser.add_argument('--template', default='templates/child-pipeline-template.yml', help="Path to the child pipeline template.")
    args = parser.parse_args()
    
    generate_pipeline(args.bom, args.config, args.template)
