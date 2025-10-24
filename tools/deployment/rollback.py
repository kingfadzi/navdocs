#!/usr/bin/env python3
"""
PPM Rollback Module
Handles rollback deployments using manifest-based discovery from GitLab artifacts or local files.
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path
import zipfile
import shutil
import json

from .utils import load_yaml, load_config, apply_default_credentials
from ..config.validation import validate_bom
from ..executors import get_executor

def get_bom_section(bom_file, deployment_type):
    """Load the full BOM and return it as the section (BOMs are flat, not nested)."""
    full_bom = load_yaml(bom_file)
    # BOMs are flat files - the entire BOM is the section for the deployment type
    return full_bom, full_bom


def download_gitlab_artifacts(pipeline_id, output_dir):
    """Downloads artifacts from a GitLab pipeline."""
    # ... (GitLab download logic remains the same)
    if os.environ.get('CI_JOB_TOKEN'):
        gitlab_token = os.environ.get('CI_JOB_TOKEN')
        auth_header = 'JOB-TOKEN'
    elif os.environ.get('GITLAB_API_TOKEN'):
        gitlab_token = os.environ.get('GITLAB_API_TOKEN')
        auth_header = 'PRIVATE-TOKEN'
    else:
        print("Error: Set CI_JOB_TOKEN (in pipeline) or GITLAB_API_TOKEN (for manual use)")
        sys.exit(1)

    project_id = os.environ.get('CI_PROJECT_ID')
    gitlab_api_url = os.environ.get('CI_API_V4_URL')

    if not all([project_id, gitlab_api_url]):
        print("Error: CI_PROJECT_ID and CI_API_V4_URL must be set for GitLab rollback.")
        sys.exit(1)

    print(f"Fetching jobs from pipeline {pipeline_id}...")
    jobs_url = f"{gitlab_api_url}/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    cmd = ['curl', '-sS', '--fail', '--header', f'{auth_header}: {gitlab_token}', jobs_url]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error fetching pipeline jobs: {result.stderr}")
        sys.exit(1)

    jobs = json.loads(result.stdout)
    archive_job = next((job for job in jobs if 'archive' in job.get('name', '').lower() and job.get('status') == 'success'), None)

    if not archive_job:
        print(f"Error: No successful archive job found in pipeline {pipeline_id}")
        sys.exit(1)

    job_id = archive_job['id']
    print(f"Found archive job: {archive_job['name']} (job #{job_id})")

    artifacts_url = f"{gitlab_api_url}/projects/{project_id}/jobs/{job_id}/artifacts"
    temp_zip = output_dir / "pipeline-artifacts.zip"
    print(f"Downloading artifacts from pipeline {pipeline_id}...")
    cmd = ['curl', '-sS', '--fail', '--header', f'{auth_header}: {gitlab_token}', '--output', str(temp_zip), artifacts_url]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error downloading artifacts: {result.stderr}")
        sys.exit(1)

    print(f"Downloaded artifacts to {temp_zip}")
    with zipfile.ZipFile(temp_zip, 'r') as zipf:
        zipf.extractall(output_dir)
    os.remove(temp_zip)
    print(f"Extracted artifacts to: {output_dir}")
    return output_dir


def validate_rollback_manifest(manifest, bom_target_server):
    """Validate that the artifact's target server matches the BOM's target server."""
    manifest_target = manifest.get('deployment_metadata', {}).get('target_server')
    print(f"Validating manifest...")
    print(f"  - Manifest target: {manifest_target}")
    print(f"  - BOM target:      {bom_target_server}")
    if manifest_target != bom_target_server:
        print("\nERROR: Target server mismatch!")
        print(f"The rollback archive was for '{manifest_target}', but the BOM targets '{bom_target_server}'.")
        sys.exit(1)
    print("  ✓ Target server matches.")


def execute_rollback_from_archive(archive_path, target_url, import_script, target_server_config, config):
    """Core logic to perform the rollback from an extracted archive."""
    extract_dir = archive_path.parent / "deployment-extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        zipf.extractall(extract_dir)
    print(f"Extracted bundle to: {extract_dir}")

    flags_file = extract_dir / "flags.txt"
    if not flags_file.exists():
        print("Error: flags.txt not found in archive.")
        sys.exit(1)

    with open(flags_file, 'r') as f:
        flags = f.read().strip()
    print(f"Using original deployment flags: {flags}")

    bundle_files = list((extract_dir / "bundles").glob("*.xml"))
    print(f"Found {len(bundle_files)} bundles to import.\n")

    # Get executor for target server
    executor = get_executor(config, target_server_config)

    for bundle in bundle_files:
        # Pass server_config for credential resolution
        executor.import_bundle(import_script, target_url, str(bundle), flags, 'charset', 'nochange', target_server_config)

    print("\nCleaning up temporary files...")
    shutil.rmtree(extract_dir.parent)


def _validate_bom_for_rollback(bom_file):
    """Validate BOM file for rollback."""
    print("\n=== VALIDATING BOM FOR ROLLBACK ===")
    is_valid, errors = validate_bom(bom_file)
    if not is_valid:
        print("BOM validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    print("✓ BOM validation successful\n")


def _load_rollback_config(bom_file, deployment_type):
    """Load and validate rollback configuration."""
    root = Path(__file__).parent.parent.parent
    bom_section, full_bom = get_bom_section(bom_file, deployment_type)
    target_server = full_bom.get('target_server')
    rollback_pipeline_id = bom_section.get('rollback_pipeline_id')

    if not all([target_server, rollback_pipeline_id]):
        print("ERROR: Missing 'target_server' or 'rollback_pipeline_id' in BOM")
        sys.exit(1)

    config = load_config()
    target_url = config['servers'][target_server]['url']
    target_server_config = config['servers'][target_server]
    apply_default_credentials(target_server_config, config)
    import_script = config['kmigrator']['import_script']

    return root, target_server, rollback_pipeline_id, config, target_url, target_server_config, import_script


def _try_local_rollback(root):
    """Try to load rollback manifest from local archives."""
    manifest_path = root / "archives" / "ROLLBACK_MANIFEST.yaml"
    if not manifest_path.exists():
        print("ERROR: ROLLBACK_MANIFEST.yaml not found in archives/")
        print("Hint: Run 'deploy' command first to generate local artifacts")
        sys.exit(1)
    return load_yaml(manifest_path), 'local', None


def _try_gitlab_rollback(root, rollback_pipeline_id):
    """Try to load rollback manifest from GitLab artifacts."""
    rollback_dir = root / "rollback-temp"
    if rollback_dir.exists():
        shutil.rmtree(rollback_dir)
    rollback_dir.mkdir()

    download_gitlab_artifacts(rollback_pipeline_id, rollback_dir)
    manifest_path = rollback_dir / "archives" / "ROLLBACK_MANIFEST.yaml"

    if not manifest_path.exists():
        raise FileNotFoundError("ROLLBACK_MANIFEST not in GitLab artifacts")

    print("✓ Found manifest in GitLab artifacts")
    return load_yaml(manifest_path), 'gitlab', rollback_dir


def _try_s3_rollback(root, rollback_pipeline_id, config, target_server):
    """Try to load rollback manifest and archive from S3."""
    from storage import get_storage_backend
    storage = get_storage_backend(config)
    temp_dir = root / "rollback-temp"
    temp_dir.mkdir(exist_ok=True)

    # Download manifest from S3
    s3_manifest_key = f"snapshots/{rollback_pipeline_id}/archives/ROLLBACK_MANIFEST.yaml"
    local_manifest_path = temp_dir / "ROLLBACK_MANIFEST.yaml"

    print("Downloading ROLLBACK_MANIFEST from S3...")
    try:
        storage.download_file(s3_manifest_key, local_manifest_path)
        manifest = load_yaml(local_manifest_path)
        print("✓ Found manifest in S3")

        validate_rollback_manifest(manifest, target_server)

        # Download archive from S3
        s3_archive_url = manifest.get('s3_archive_url')
        if not s3_archive_url:
            print("ERROR: ROLLBACK_MANIFEST missing s3_archive_url")
            sys.exit(1)

        s3_key = s3_archive_url.replace(f"s3://{config['s3']['bucket_name']}/", "")
        local_archive = temp_dir / Path(s3_key).name

        print(f"Downloading archive from S3: {s3_archive_url}")
        storage.download_file(s3_key, local_archive)

        return manifest, 's3', local_archive

    except Exception as e:
        print(f"ERROR: Failed to retrieve from S3: {e}")
        print(f"Tried: s3://{config['s3']['bucket_name']}/{s3_manifest_key}")
        print("Possible causes: Missing snapshot, incorrect pipeline ID, or deleted objects")
        sys.exit(1)


def _get_local_archive(root, manifest):
    """Get archive path for local rollback."""
    archive_path_str = manifest.get('rollback_bundle_path')
    archive_path = root / archive_path_str
    if not archive_path.exists():
        print(f"ERROR: Local archive not found at {archive_path}")
        sys.exit(1)

    temp_dir = root / "rollback-temp"
    temp_dir.mkdir(exist_ok=True)
    temp_archive = temp_dir / archive_path.name
    shutil.copy(archive_path, temp_archive)
    return temp_archive


def rollback(bom_file, deployment_type):
    """Main rollback function with GitLab → S3 → Local fallback."""
    _validate_bom_for_rollback(bom_file)

    root, target_server, rollback_pipeline_id, config, target_url, target_server_config, import_script = \
        _load_rollback_config(bom_file, deployment_type)

    print(f"\n=== ROLLBACK DEPLOYMENT ({deployment_type.upper()}) ===")
    print(f"Target: {target_server}, Pipeline ID: {rollback_pipeline_id}\n")

    # Try rollback sources in order: Local → GitLab → S3
    manifest = None
    manifest_source = None
    local_archive = None

    if str(rollback_pipeline_id).lower() == 'local':
        print("Mode: Local")
        manifest, manifest_source, _ = _try_local_rollback(root)
        local_archive = _get_local_archive(root, manifest)
    else:
        # Try GitLab first
        try:
            print("Attempting rollback from GitLab artifacts...")
            manifest, manifest_source, rollback_dir = _try_gitlab_rollback(root, rollback_pipeline_id)

            # Get archive from GitLab
            archive_path = rollback_dir / manifest.get('rollback_bundle_path')
            if archive_path.exists():
                print(f"✓ Using archive from GitLab: {archive_path.name}")
                local_archive = archive_path
            else:
                raise FileNotFoundError("Archive not in GitLab artifacts")

        except Exception as e:
            print(f"GitLab not available: {e}")
            print("Attempting S3 fallback...")
            manifest, manifest_source, local_archive = _try_s3_rollback(root, rollback_pipeline_id, config, target_server)

    # Validate manifest if not already validated
    if manifest_source != 's3':
        validate_rollback_manifest(manifest, target_server)

    # Execute rollback
    print(f"\nRollback source: {manifest_source.upper()}")
    execute_rollback_from_archive(local_archive, target_url, import_script, target_server_config, config)

    print("\n=== ROLLBACK COMPLETE ===")
