#!/usr/bin/env python3
"""
PPM Deployment Orchestrator
Extracts and imports PPM entities across environments
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path
import glob
import zipfile
import shutil
from datetime import datetime
import argparse
from validate_bom import validate_bom
import rollback


def load_yaml(file_path):
    """Load YAML file and return contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def save_deployment_metadata(metadata, output_path="bundles/deployment-metadata.yaml"):
    """Save deployment state for passing between pipeline stages. (DEMO VERSION)"""
    Path(output_path).parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, 'w') as f:
        yaml.dump(metadata, f, default_flow_style=False)
    print(f"[DEMO] Saved metadata: {output_path}")


def load_deployment_metadata(metadata_path="bundles/deployment-metadata.yaml"):
    """Load deployment state from previous pipeline stage. (DEMO VERSION)"""
    if not Path(metadata_path).exists():
        print(f"[DEMO] Error: Metadata file not found: {metadata_path}")
        sys.exit(1)
    return load_yaml(metadata_path)


def get_flag_string(profile_name):
    """
    Get compiled flag string from profile.
    Calls flag_compiler.py and returns the 25-character Y/N string.
    (DEMO VERSION)
    """
    script_dir = Path(__file__).parent
    compiler = script_dir / "flag_compiler.py"
    result = subprocess.run(
        ['python3', str(compiler), profile_name],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def run_extract(script_path, url, entity_id, reference_code=None):
    """Extract entity (DEMO STUB)"""
    print(f"[DEMO] Extracting entity {entity_id}")
    return f"./bundles/KMIGRATOR_EXTRACT_{entity_id}_demo.xml"


def run_import(script_path, url, bundle_file, flags, i18n, refdata):
    """Import bundle (DEMO STUB)"""
    print(f"[DEMO] Importing {bundle_file}")


def create_evidence_package(bom_file, archive_path, config):
    """Create evidence package (DEMO STUB)"""
    print(f"[DEMO] Creating evidence package")
    return Path("evidence/demo-evidence.zip")


def archive_deployment(bundles, bom_file, flags, config):
    """Create archive (DEMO STUB)"""
    print(f"[DEMO] Creating deployment archive")
    return Path("archives/demo-archive.zip")


def print_gitlab_artifact_info(archive_path, bom_file, metadata):
    """Print rollback info (DEMO STUB)"""
    print(f"[DEMO] Rollback information printed")


def extract_command(bom_file, deployment_type):
    """PHASE 1: Extract (DEMO STUB)"""
    print(f"[DEMO] PHASE 1: EXTRACT ({deployment_type.upper()})")
    root = Path(__file__).parent.parent
    bom = load_yaml(bom_file)
    metadata = {
        'deployment_type': deployment_type,
        'profile': bom.get('profile'),
        'source_server': bom.get('source_server'),
        'target_server': bom.get('target_server'),
        'flags': 'YYYYYNNNNYYYYYNNNNNNNNNNN',
        'bundles': ['./bundles/demo.xml'],
        'bom_file': str(bom_file),
        'i18n_mode': 'charset',
        'refdata_mode': 'nochange'
    }
    save_deployment_metadata(metadata, f"bundles/{deployment_type}-metadata.yaml")


def import_command(bom_file, deployment_type):
    """PHASE 2: Import (DEMO STUB)"""
    print(f"[DEMO] PHASE 2: IMPORT ({deployment_type.upper()})")
    load_deployment_metadata(f"bundles/{deployment_type}-metadata.yaml")


def archive_command(bom_file, deployment_type):
    """PHASE 3: Archive (DEMO STUB)"""
    print(f"[DEMO] PHASE 3: ARCHIVE ({deployment_type.upper()})")
    load_deployment_metadata(f"bundles/{deployment_type}-metadata.yaml")

def create_rollback_manifest(archive_path, metadata, bom_file):
    """Create rollback manifest (DEMO STUB)"""
    print(f"[DEMO] Creating rollback manifest")

def validate_bom_before_action(bom_file):
    """Validate BOM (DEMO STUB)"""
    print(f"[DEMO] VALIDATING BOM")
    validate_bom(bom_file)


def deploy_command(bom_file, deployment_type):
    """Deploy (DEMO STUB)"""
    print(f"[DEMO] DEPLOYMENT ({deployment_type.upper()})")
    validate_bom_before_action(bom_file)
    extract_command(bom_file, deployment_type)
    import_command(bom_file, deployment_type)
    archive_command(bom_file, deployment_type)

def main():
    """Main entry point - parse command line and run deployment."""
    parser = argparse.ArgumentParser(
        description='PPM Deployment Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full deployment command (for local testing)
  deploy.py deploy --type baseline --bom boms/baseline.yaml
  deploy.py deploy --type functional --bom boms/functional.yaml

  # CI/CD pipeline stage commands
  deploy.py extract --type baseline --bom boms/baseline.yaml
  deploy.py import --type baseline --bom boms/baseline.yaml
  deploy.py archive --type baseline --bom boms/baseline.yaml

  # Manual rollback command
  deploy.py rollback --type functional --bom boms/functional.yaml
        """
    )
    parser.add_argument('command', choices=['extract', 'import', 'archive', 'rollback', 'deploy'], help='Deployment command')
    parser.add_argument('--bom', required=True, help='BOM file path (e.g., boms/baseline.yaml or boms/functional.yaml)')
    parser.add_argument('--type', choices=['baseline', 'functional'], help="Deployment type")
    args = parser.parse_args()

    if args.command in ['extract', 'import', 'archive', 'deploy', 'rollback'] and not args.type:
        parser.error(f"{args.command} requires --type argument (baseline or functional)")

    if args.command == 'extract':
        extract_command(args.bom, args.type)
    elif args.command == 'import':
        import_command(args.bom, args.type)
    elif args.command == 'archive':
        archive_command(args.bom, args.type)
    elif args.command == 'deploy':
        deploy_command(args.bom, args.type)
    elif args.command == 'rollback':
        rollback.rollback(args.bom, args.type)

if __name__ == '__main__':
    main()
