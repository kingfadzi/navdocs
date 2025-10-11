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
from storage import get_storage_backend
from remote_executor import RemoteExecutor


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
    root = Path(__file__).parent.parent
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
    Calls flag_compiler.py and returns the 25-character Y/N string.
    """
    script_dir = Path(__file__).parent
    compiler = script_dir / "flag_compiler.py"
    result = subprocess.run(
        ['python3', str(compiler), profile_name],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def is_remote_mode(server_config, config):
    """Check if we're using remote execution + storage backend."""
    return (
        server_config.get('ssh_host') is not None and
        config['deployment'].get('storage_backend', 'local') != 'local'
    )


def run_extract(script_path, url, entity_id, reference_code=None, server_config=None, config=None):
    """
    Extract entity - local or remote+storage mode.
    Returns local file path (local mode) or S3 metadata dict (remote mode).
    """
    # LOCAL MODE - existing behavior
    if not server_config or not config or not is_remote_mode(server_config, config):
        return _run_extract_local(script_path, url, entity_id, reference_code)

    # REMOTE + STORAGE MODE
    return _run_extract_remote(script_path, url, entity_id, reference_code, server_config, config)


def _run_extract_local(script_path, url, entity_id, reference_code=None):
    """Extract entity locally (mock mode)."""
    username = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
    password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')

    if not username or not password:
        print("ERROR: PPM credentials not set")
        print("  Required: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD")
        sys.exit(1)

    print(f"✓ Credentials loaded (user={username[:3]}...{username[-2:]}, password={'*' * len(password)})")

    cmd = [
        'bash', script_path, '-username', username, '-password', password,
        '-url', url, '-action', 'Bundle', '-entityId', str(entity_id)
    ]
    if reference_code:
        cmd.extend(['-referenceCode', reference_code])

    print(f"Extracting entity {entity_id}" + (f" ({reference_code})" if reference_code else " (ALL)") + f" from {url} (LOCAL)")
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(result.stdout)

    for line in result.stdout.split('\n'):
        if 'Bundle saved to:' in line:
            return line.split('Bundle saved to:')[1].strip()

    pattern = f"./bundles/KMIGRATOR_EXTRACT_{entity_id}_*.xml"
    files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def _run_extract_remote(script_path, url, entity_id, reference_code, server_config, config):
    """Extract entity remotely and upload to storage."""
    username = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
    password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')

    if not username or not password:
        print("ERROR: PPM credentials not set")
        print("  Required: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD")
        sys.exit(1)

    print(f"✓ Credentials loaded (user={username[:3]}...{username[-2:]}, password={'*' * len(password)})")

    # Initialize storage and remote executor
    storage = get_storage_backend(config)
    ssh_executor = RemoteExecutor()

    # Generate bundle filename
    pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    if reference_code:
        bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}_{reference_code}_{timestamp}.xml"
    else:
        bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}_{timestamp}.xml"

    remote_bundle_dir = f"/tmp/ppm-bundles-{pipeline_id}"
    remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"
    storage_key = f"bundles/{pipeline_id}/{bundle_filename}"

    ssh_host = server_config['ssh_host']

    print(f"Extracting entity {entity_id}" + (f" ({reference_code})" if reference_code else " (ALL)") + f" from {url} (REMOTE → S3)")
    print(f"Remote: {username}@{ssh_host}")

    try:
        # Step 1: Create remote directory
        ssh_executor.ssh_exec_check(server_config, f"mkdir -p {remote_bundle_dir}")

        # Step 2: Build and execute kMigrator command
        kmigrator_cmd = (
            f"{script_path} -username {username} -password {password} "
            f"-url {url} -action Bundle -entityId {entity_id}"
        )
        if reference_code:
            kmigrator_cmd += f" -referenceCode {reference_code}"
        kmigrator_cmd += f" -filename {remote_bundle_file}"

        print(f"Executing kMigrator...\n")
        stdout, stderr, returncode = ssh_executor.ssh_exec(server_config, kmigrator_cmd)

        if returncode != 0:
            print(f"ERROR: kMigrator extract failed: {stderr}")
            sys.exit(1)

        print(stdout)

        # Step 3: Upload to storage
        bundle_metadata = storage.upload_from_server(
            ssh_executor, server_config, remote_bundle_file, storage_key
        )

        # Step 4: Cleanup remote directory
        ssh_executor.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")

        return bundle_metadata

    except Exception as e:
        print(f"ERROR: Remote extraction failed: {e}")
        # Cleanup on error
        ssh_executor.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")
        sys.exit(1)


def run_import(script_path, url, bundle_metadata, flags, i18n, refdata, server_config=None, config=None):
    """
    Import bundle - local or remote+storage mode.
    bundle_metadata: local file path (string) or S3 metadata (dict)
    """
    # LOCAL MODE - existing behavior
    if not server_config or not config or not is_remote_mode(server_config, config):
        return _run_import_local(script_path, url, bundle_metadata, flags, i18n, refdata)

    # REMOTE + STORAGE MODE
    return _run_import_remote(script_path, url, bundle_metadata, flags, i18n, refdata, server_config, config)


def _run_import_local(script_path, url, bundle_file, flags, i18n, refdata):
    """Import bundle locally (mock mode)."""
    username = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
    password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')

    if not username or not password:
        print("ERROR: PPM credentials not set")
        print("  Required: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD")
        sys.exit(1)

    print(f"✓ Credentials loaded (user={username[:3]}...{username[-2:]}, password={'*' * len(password)})")

    cmd = [
        'bash', script_path, '-username', username, '-password', password,
        '-url', url, '-action', 'import', '-filename', bundle_file,
        '-i18n', i18n, '-refdata', refdata, '-flags', flags
    ]
    print(f"Importing {bundle_file} to {url} (LOCAL)")
    print(f"Command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(result.stdout)


def _run_import_remote(script_path, url, bundle_metadata, flags, i18n, refdata, server_config, config):
    """Import bundle from storage to remote server."""
    username = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
    password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')

    if not username or not password:
        print("ERROR: PPM credentials not set")
        print("  Required: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD")
        sys.exit(1)

    print(f"✓ Credentials loaded (user={username[:3]}...{username[-2:]}, password={'*' * len(password)})")

    # Initialize storage and remote executor
    storage = get_storage_backend(config)
    ssh_executor = RemoteExecutor()

    # Extract bundle info from metadata
    bundle_filename = bundle_metadata.get('bundle_filename')

    # Generate remote paths
    pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
    remote_bundle_dir = f"/tmp/ppm-bundles-{pipeline_id}"
    remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"

    ssh_host = server_config['ssh_host']

    print(f"Importing {bundle_filename} to {url} (S3 → REMOTE)")
    print(f"Remote: {username}@{ssh_host}")

    try:
        # Step 1: Create remote directory
        ssh_executor.ssh_exec_check(server_config, f"mkdir -p {remote_bundle_dir}")

        # Step 2: Download bundle from storage to remote server
        storage.download_to_server(ssh_executor, server_config, bundle_metadata, remote_bundle_file)

        # Step 3: Execute kMigrator import
        kmigrator_cmd = (
            f"{script_path} -username {username} -password {password} "
            f"-url {url} -action import -filename {remote_bundle_file} "
            f"-i18n {i18n} -refdata {refdata} -flags {flags}"
        )

        print(f"Executing kMigrator import...\n")
        stdout, stderr, returncode = ssh_executor.ssh_exec(server_config, kmigrator_cmd)

        if returncode != 0:
            print(f"ERROR: kMigrator import failed: {stderr}")
            sys.exit(1)

        print(stdout)

        # Step 4: Cleanup remote directory
        ssh_executor.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")

    except Exception as e:
        print(f"ERROR: Remote import failed: {e}")
        # Cleanup on error
        ssh_executor.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")
        sys.exit(1)


def create_evidence_package(bom_file, archive_path, config):
    """
    Create evidence package for compliance/audit.
    """
    root = Path(__file__).parent.parent
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    bom = load_yaml(bom_file)
    change_request = bom.get('change_request', 'baseline')
    target_server = bom.get('target_server', 'unknown')
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    evidence_name = f"{change_request}-{target_server}-{timestamp}-evidence.zip"
    evidence_path = evidence_dir / evidence_name
    print(f"Creating evidence package: {evidence_name}")
    with zipfile.ZipFile(evidence_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(bom_file, arcname="bom-deployed.yaml")
        if Path(archive_path).exists():
            with zipfile.ZipFile(archive_path, 'r') as archive_zip:
                zipf.writestr("archive-manifest.yaml", archive_zip.read("manifest.yaml"))
        metadata = {
            'bom_file': str(bom_file), 'archive_path': str(archive_path),
            'deployment_timestamp': datetime.now().isoformat(),
            'ci_commit_sha': os.environ.get('CI_COMMIT_SHA', 'local'),
            'ci_pipeline_id': os.environ.get('CI_PIPELINE_ID', 'local'),
            'deployed_by': os.environ.get('GITLAB_USER_LOGIN', os.environ.get('USER', 'unknown'))
        }
        zipf.writestr("metadata.yaml", yaml.dump(metadata, default_flow_style=False))
    print(f"Evidence package created: {evidence_path}")
    return evidence_path


def archive_deployment(bundles, bom_file, flags, config):
    """
    Create a ZIP archive with bundles + BOM + flags for rollback.
    """
    root = Path(__file__).parent.parent
    archive_dir = root / config['deployment']['archive_dir']
    archive_dir.mkdir(exist_ok=True)
    bom = load_yaml(bom_file)
    version = bom.get('version', 'unknown')
    change_request = bom.get('change_request', 'baseline')
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    archive_name = f"{change_request}-v{version}-{timestamp}-bundles.zip"
    archive_path = archive_dir / archive_name
    print(f"Creating deployment archive: {archive_name}")
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for bundle in bundles:
            zipf.write(bundle, arcname=f"bundles/{Path(bundle).name}")
        zipf.write(bom_file, arcname="bom.yaml")
        zipf.writestr("flags.txt", flags)
        manifest = {
            'version': version, 'change_request': change_request,
            'archived_at': datetime.now().isoformat(),
            'bundles': [Path(b).name for b in bundles], 'flags': flags
        }
        zipf.writestr("manifest.yaml", yaml.dump(manifest))
    print(f"Archive created: {archive_path}")
    return archive_path


def print_gitlab_artifact_info(archive_path, bom_file, metadata):
    """
    Print GitLab artifact information for manual rollback reference.
    """
    archive_name = Path(archive_path).name
    pipeline_id = os.environ.get('CI_PIPELINE_ID', 'N/A')
    print("=" * 60)
    print("ROLLBACK INFORMATION")
    print("=" * 60)
    print(f"Archive created: {archive_name}")
    if pipeline_id != 'N/A':
        print(f"To rollback, add to your BOM: rollback_pipeline_id: {pipeline_id}")
    print(f"  - Profile: {metadata.get('profile', 'unknown')}")
    print(f"  - Target: {metadata.get('target_server', 'unknown')}")
    print("=" * 60)


def extract_command(bom_file, deployment_type):
    """PHASE 1: Extract entities and save metadata."""
    print("=" * 60)
    print(f"PHASE 1: EXTRACT ({deployment_type.upper()})")
    print("=" * 60)
    root = Path(__file__).parent.parent
    bom = load_yaml(bom_file)
    profile_name = bom['profile']
    source_server = bom['source_server']
    target_server = bom['target_server']

    is_baseline = 'baseline' in profile_name.lower()
    config = load_config()
    source_url = config['servers'][source_server]['url']
    source_server_config = config['servers'][source_server]
    extract_script = config['kmigrator']['extract_script']
    flags = get_flag_string(profile_name)

    # Determine storage mode
    storage_mode = 'local'
    if is_remote_mode(source_server_config, config):
        storage_mode = config['deployment'].get('storage_backend', 'local')

    print(f"Source: {source_server}, Target: {target_server}, Profile: {profile_name}")
    print(f"Storage: {storage_mode.upper()}")
    print(f"Flags: {flags}\n")

    bundles = []
    if is_baseline:
        profile = load_yaml(root / "profiles" / f"{profile_name}.yaml")
        print(f"Extracting {len(profile['entities'])} baseline entity types...\n")
        for entity in profile['entities']:
            bundle = run_extract(extract_script, source_url, entity['id'],
                               server_config=source_server_config, config=config)
            bundles.append(bundle)
    else:
        print(f"Extracting {len(bom['entities'])} functional entities...\n")
        for entity in bom['entities']:
            bundle = run_extract(extract_script, source_url, entity['entity_id'],
                               entity['reference_code'],
                               server_config=source_server_config, config=config)
            bundles.append(bundle)

    metadata = {
        'deployment_type': deployment_type,
        'profile': profile_name,
        'source_server': source_server,
        'target_server': target_server,
        'flags': flags,
        'bundles': bundles,  # Either local paths or S3 metadata dicts
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
    print("=" * 60)
    print(f"PHASE 2: IMPORT ({deployment_type.upper()})")
    print("=" * 60)
    metadata = load_deployment_metadata(f"bundles/{deployment_type}-metadata.yaml")
    target_server = metadata['target_server']
    flags = metadata['flags']
    bundles = metadata['bundles']
    i18n_mode = metadata['i18n_mode']
    refdata_mode = metadata['refdata_mode']
    storage_mode = metadata.get('storage_mode', 'local')

    root = Path(__file__).parent.parent
    config = load_config()
    target_url = config['servers'][target_server]['url']
    target_server_config = config['servers'][target_server]
    import_script = config['kmigrator']['import_script']

    print(f"Target: {target_server}, Storage: {storage_mode.upper()}, Bundles: {len(bundles)}")
    print(f"Flags: {flags}\n")
    print(f"Importing {len(bundles)} bundles...\n")

    for bundle in bundles:
        run_import(import_script, target_url, bundle, flags, i18n_mode, refdata_mode,
                  server_config=target_server_config, config=config)

    print(f"\n✓ Imported {len(bundles)} bundles for {deployment_type}")
    print("=" * 60)


def archive_command(bom_file, deployment_type):
    """PHASE 3: Archive and create evidence."""
    print("=" * 60)
    print(f"PHASE 3: ARCHIVE ({deployment_type.upper()})")
    print("=" * 60)
    metadata = load_deployment_metadata(f"bundles/{deployment_type}-metadata.yaml")
    root = Path(__file__).parent.parent
    config = load_config()
    archive_path = archive_deployment(metadata['bundles'], metadata['bom_file'], metadata['flags'], config)
    create_rollback_manifest(archive_path, metadata, metadata['bom_file'])
    print_gitlab_artifact_info(archive_path, metadata['bom_file'], metadata)
    create_evidence_package(metadata['bom_file'], archive_path, config)
    bundle_dir = root / "bundles"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
        print(f"Deleted directory: {bundle_dir}")
    print("=" * 60)
    print(f"ARCHIVE COMPLETE for {deployment_type}")
    print("=" * 60)

def create_rollback_manifest(archive_path, metadata, bom_file):
    """Create ROLLBACK_MANIFEST.yaml inside the archives directory."""
    root = Path(__file__).parent.parent
    archive_dir = root / "archives"
    archive_dir.mkdir(exist_ok=True) # Ensure the directory exists
    manifest_path = archive_dir / "ROLLBACK_MANIFEST.yaml"
    manifest = {
        'rollback_bundle_path': str(archive_path.relative_to(root)),
        'deployment_metadata': {
            'deployment_type': metadata.get('deployment_type'),
            'profile': metadata.get('profile'),
            'target_server': metadata.get('target_server'),
            'bom_version': metadata.get('bom_version'),
            'change_request': metadata.get('change_request'),
            'flags': metadata.get('flags')
        },
        'git_context': {
            'commit_sha': os.environ.get('CI_COMMIT_SHA', 'local'),
            'pipeline_id': os.environ.get('CI_PIPELINE_ID', 'local'),
        },
        'manifest_version': '1.0.0',
        'created_at': datetime.now().isoformat()
    }
    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
    print(f"Created rollback manifest: {manifest_path}")

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


def deploy_command(bom_file, deployment_type):
    """
    One-shot deployment that runs the full extract -> import -> archive sequence.
    """
    # First, validate the BOM file.
    validate_bom_before_action(bom_file)

    print("=" * 60)
    print(f"DEPLOYMENT ({deployment_type.upper()})")
    print("=" * 60)
    print()

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
