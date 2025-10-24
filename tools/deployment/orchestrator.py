#!/usr/bin/env python3
"""
PPM Deployment Orchestrator
Extracts and imports PPM entities across environments
"""

import sys
import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime

from .utils import (
    load_yaml, load_config,
    save_deployment_metadata, load_deployment_metadata,
    get_flag_string, validate_bom_before_action,
    get_vault_config_command, apply_default_credentials,
    get_ppm_credentials
)
from .archive import (
    archive_deployment, create_evidence_package,
    create_complete_snapshot, create_rollback_manifest,
    print_gitlab_artifact_info
)
from . import rollback
from ..executors import get_executor


def _print_phase(phase_num, phase_name, deployment_type=None):
    """Helper to print phase headers."""
    if deployment_type:
        print(f"\n{'='*60}")
        print(f"PHASE {phase_num}: {phase_name} ({deployment_type.upper()})")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"{phase_name}")
        print(f"{'='*60}")


def extract_command(bom_file, deployment_type):
    """PHASE 1: Extract entities and save metadata."""
    _print_phase(1, "EXTRACT", deployment_type)
    root = Path(__file__).parent.parent.parent
    bom = load_yaml(bom_file)
    profile_name = bom['profile']
    source_server = bom['source_server']
    target_server = bom['target_server']

    is_baseline = 'baseline' in profile_name.lower()
    config = load_config()
    source_url = config['servers'][source_server]['url']
    source_server_config = config['servers'][source_server]
    apply_default_credentials(source_server_config, config)
    extract_script = config['kmigrator']['extract_script']
    flags = get_flag_string(profile_name)

    # Get executor for source server
    executor = get_executor(config, source_server_config)

    # Determine storage mode (for metadata tracking)
    storage_mode = config['deployment'].get('storage_backend', 'local')

    print(f"Source: {source_server}, Target: {target_server}, Profile: {profile_name}")
    print(f"Storage: {storage_mode.upper()}")
    print(f"Flags: {flags}\n")

    bundles = []
    if is_baseline:
        profile = load_yaml(root / "profiles" / f"{profile_name}.yaml")
        print(f"Extracting {len(profile['entities'])} baseline entity types...\n")
        for entity in profile['entities']:
            # Pass server_config for credential resolution
            # Returns local file path (both LocalExecutor and RemoteKMigratorExecutor)
            bundle = executor.extract(extract_script, source_url, entity['id'], None, source_server_config)
            bundles.append(bundle)
    else:
        print(f"Extracting {len(bom['entities'])} functional entities...\n")
        for entity in bom['entities']:
            # Pass server_config for credential resolution
            # Returns local file path (both LocalExecutor and RemoteKMigratorExecutor)
            bundle = executor.extract(extract_script, source_url, entity['entity_id'], entity['reference_code'], source_server_config)
            bundles.append(bundle)

    metadata = {
        'deployment_type': deployment_type,
        'profile': profile_name,
        'source_server': source_server,
        'target_server': target_server,
        'flags': flags,
        'bundles': bundles,  # Local paths (always available as GitLab artifacts)
        'storage_mode': storage_mode,
        'bom_file': str(bom_file),
        'bom_version': bom.get('version', 'unknown'),
        'change_request': bom.get('change_request', 'N/A'),
        'extracted_at': datetime.now().isoformat(),
        'i18n_mode': 'none' if is_baseline else 'charset',
        'refdata_mode': 'nochange'
    }
    save_deployment_metadata(metadata, f"bundles/{deployment_type}-metadata.yaml")
    print(f"\n✓ Extracted {len(bundles)} bundles for {deployment_type}")
    print("=" * 60)


def import_command(bom_file, deployment_type):
    """PHASE 2: Import bundles to target server."""
    _print_phase(2, "IMPORT", deployment_type)
    metadata = load_deployment_metadata(f"bundles/{deployment_type}-metadata.yaml")
    target_server = metadata['target_server']
    flags = metadata['flags']
    bundles = metadata['bundles']  # Always local paths from GitLab artifacts
    i18n_mode = metadata['i18n_mode']
    refdata_mode = metadata['refdata_mode']
    storage_mode = metadata.get('storage_mode', 'local')

    config = load_config()
    target_url = config['servers'][target_server]['url']
    target_server_config = config['servers'][target_server]
    apply_default_credentials(target_server_config, config)
    import_script = config['kmigrator']['import_script']

    # Get executor for target server
    executor = get_executor(config, target_server_config)

    print(f"Target: {target_server}, Storage: {storage_mode.upper()}, Bundles: {len(bundles)}")
    print(f"Flags: {flags}\n")
    print(f"Importing {len(bundles)} bundles from GitLab artifacts...\n")

    for bundle in bundles:
        # Bundles are always local file paths (from GitLab artifacts)
        # Pass server_config for credential resolution
        executor.import_bundle(import_script, target_url, bundle, flags, i18n_mode, refdata_mode, target_server_config)

    print(f"\n✓ Imported {len(bundles)} bundles for {deployment_type}")
    print("=" * 60)


def archive_command(bom_file, deployment_type):
    """PHASE 3: Archive and create evidence."""
    _print_phase(3, "ARCHIVE", deployment_type)

    metadata = load_deployment_metadata(f"bundles/{deployment_type}-metadata.yaml")
    root = Path(__file__).parent.parent.parent
    config = load_config()
    storage_mode = config['deployment'].get('storage_backend', 'local')
    pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')

    # Step 1: Create rollback archive ZIP
    archive_path = archive_deployment(metadata['bundles'], metadata['bom_file'], metadata['flags'], config)

    # Step 2: Create evidence package
    evidence_path = create_evidence_package(metadata['bom_file'], archive_path, config)

    # Step 3: Create ROLLBACK_MANIFEST (before S3 upload, so it can be included in snapshot)
    # Note: s3_snapshot_url will be populated after upload, manifest will be updated
    create_rollback_manifest(archive_path, storage_mode, metadata, metadata['bom_file'], s3_snapshot_url=None)

    # Step 4: Create complete snapshot and upload to S3 (includes ROLLBACK_MANIFEST)
    s3_snapshot_url = create_complete_snapshot(
        pipeline_id, deployment_type, metadata,
        metadata['bom_file'], archive_path, evidence_path, config
    )

    # Step 5: Update ROLLBACK_MANIFEST with S3 snapshot URL
    if s3_snapshot_url:
        create_rollback_manifest(archive_path, storage_mode, metadata, metadata['bom_file'], s3_snapshot_url)

    # Step 5: Print rollback info
    print_gitlab_artifact_info(archive_path, metadata['bom_file'], metadata)

    # Step 6: Cleanup temporary bundles
    bundle_dir = root / "bundles"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
        print(f"Deleted directory: {bundle_dir}")

    print("=" * 60)
    print(f"ARCHIVE COMPLETE for {deployment_type}")
    print("=" * 60)


def validate_command(bom_file):
    """Validate BOM and check environment is ready for deployment."""
    _print_phase(None, "VALIDATING DEPLOYMENT PREREQUISITES")

    # 1. Validate BOM file
    print("[1/3] Validating BOM file...")
    validate_bom_before_action(bom_file)
    print()

    # 2. Check servers exist in config
    print("[2/3] Checking server configuration...")
    bom = load_yaml(bom_file)
    config = load_config()

    source = bom['source_server']
    target = bom['target_server']

    if source not in config['servers']:
        print(f"✗ ERROR: Source server '{source}' not found in configuration")
        sys.exit(1)
    print(f"  ✓ Source server '{source}' found")

    if target not in config['servers']:
        print(f"✗ ERROR: Target server '{target}' not found in configuration")
        sys.exit(1)
    print(f"  ✓ Target server '{target}' found")
    print()

    # 3. Check required credentials are set
    print("[3/3] Checking credentials...")
    source_config = config['servers'][source]
    target_config = config['servers'][target]
    apply_default_credentials(source_config, config)
    apply_default_credentials(target_config, config)

    # Check source server credentials
    print(f"  Checking source server ({source})...")
    try:
        get_ppm_credentials(source_config)
    except SystemExit:
        print(f"✗ Source server credentials check failed")
        sys.exit(1)

    # Check target server credentials
    print(f"  Checking target server ({target})...")
    try:
        get_ppm_credentials(target_config)
    except SystemExit:
        print(f"✗ Target server credentials check failed")
        sys.exit(1)

    print()
    print("=" * 60)
    print("✓ ALL VALIDATION CHECKS PASSED")
    print("=" * 60)
    print()
    print(f"Ready to deploy from {source} to {target}")
    print(f"Run: python3 -m tools.deployment.orchestrator deploy --type {bom.get('profile', 'unknown')} --bom {bom_file}")


def deploy_command(bom_file, deployment_type):
    """One-shot deployment that runs the full extract -> import -> archive sequence."""
    validate_bom_before_action(bom_file)
    _print_phase(None, f"DEPLOYMENT ({deployment_type.upper()})")

    # Phase 1: Extract
    extract_command(bom_file, deployment_type)

    # Phase 2: Import
    import_command(bom_file, deployment_type)

    # Phase 3: Archive
    archive_command(bom_file, deployment_type)

    print("=" * 60)
    print(f"DEPLOYMENT ({deployment_type.upper()}) COMPLETE")
    print("=" * 60)


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

  # Get Vault config for CI/CD
  deploy.py get-vault-config --server dev-ppm-useast
        """
    )
    parser.add_argument('command', choices=['extract', 'import', 'archive', 'rollback', 'deploy', 'get-vault-config', 'validate'], help='Deployment command')
    parser.add_argument('--bom', help='BOM file path (e.g., boms/baseline.yaml or boms/functional.yaml)')
    parser.add_argument('--type', choices=['baseline', 'functional'], help="Deployment type")
    parser.add_argument('--server', help='Server name (e.g., dev-ppm-useast)')
    args = parser.parse_args()

    # Validate required arguments for each command
    if args.command in ['extract', 'import', 'archive', 'deploy', 'rollback']:
        if not args.bom:
            parser.error(f"{args.command} requires --bom argument")
        if not args.type:
            parser.error(f"{args.command} requires --type argument (baseline or functional)")

    if args.command == 'validate':
        if not args.bom:
            parser.error("validate requires --bom argument")

    if args.command == 'get-vault-config':
        if not args.server:
            parser.error("get-vault-config requires --server argument")

    # Execute command
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
    elif args.command == 'get-vault-config':
        get_vault_config_command(args.server)
    elif args.command == 'validate':
        validate_command(args.bom)


if __name__ == '__main__':
    main()
