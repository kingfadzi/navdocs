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

from deploy import run_import, load_yaml
from validate_bom import validate_bom

def get_bom_section(bom_file, deployment_type):
    """Load the full BOM and return the specific section for the deployment type."""
    full_bom = load_yaml(bom_file)
    section = full_bom.get(deployment_type)
    if not isinstance(section, dict):
        print(f"Error: Deployment type '{deployment_type}' not found or is not a valid section in {bom_file}")
        sys.exit(1)
    return section, full_bom


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


def execute_rollback_from_archive(archive_path, target_url, import_script):
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

    for bundle in bundle_files:
        run_import(import_script, target_url, str(bundle), flags, 'charset', 'nochange')

    print("\nCleaning up temporary files...")
    shutil.rmtree(extract_dir.parent)


def rollback(bom_file, deployment_type):
    """Main rollback function router."""
    # First, validate the BOM file.
    print("=" * 60)
    print("VALIDATING BOM FOR ROLLBACK")
    print("=" * 60)
    is_valid, errors = validate_bom(bom_file)
    if not is_valid:
        print("BOM validation failed. Errors:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease fix the errors in the BOM file before proceeding with rollback.")
        sys.exit(1)
    print("BOM validation successful.")
    print("=" * 60)
    print()

    root = Path(__file__).parent.parent
    bom_section, full_bom = get_bom_section(bom_file, deployment_type)
    target_server = full_bom.get('target_server')
    rollback_pipeline_id = bom_section.get('rollback_pipeline_id')

    if not all([target_server, rollback_pipeline_id]):
        print("Error: 'target_server' (top-level) and 'rollback_pipeline_id' (in section) must be specified.")
        sys.exit(1)

    config = load_yaml(root / "config" / "deployment-config.yaml")
    target_url = config['servers'][target_server]['url']
    import_script = config['kmigrator']['import_script']

    print("=" * 60)
    print(f"ROLLBACK DEPLOYMENT ({deployment_type.upper()})")
    print("=" * 60)
    print(f"Target Server: {target_server}")
    print(f"Rollback Pipeline ID: {rollback_pipeline_id}")

    # ROUTER LOGIC
    if str(rollback_pipeline_id).lower() == 'local':
        # --- LOCAL ROLLBACK ---
        print("\nMode: Local")
        manifest_path = root / "archives" / "ROLLBACK_MANIFEST.yaml"
        if not manifest_path.exists():
            print(f"Error: For local rollback, ROLLBACK_MANIFEST.yaml not found in archives/")
            print("Hint: Run a 'deploy' command first to generate local artifacts.")
            sys.exit(1)
        
        manifest = load_yaml(manifest_path)
        validate_rollback_manifest(manifest, target_server)
        
        archive_path_str = manifest.get('rollback_bundle_path')
        if not archive_path_str:
            print("Error: 'rollback_bundle_path' not found in local manifest.")
            sys.exit(1)
        
        archive_path = root / archive_path_str
        if not archive_path.exists():
            print(f"Error: Local rollback archive not found at {archive_path}")
            sys.exit(1)
            
        temp_dir = root / "rollback-temp"
        if not temp_dir.exists():
            temp_dir.mkdir()
        
        # Copy archive to a temp location to standardize the execution logic
        local_archive_copy = temp_dir / archive_path.name
        shutil.copy(archive_path, local_archive_copy)
        
        execute_rollback_from_archive(local_archive_copy, target_url, import_script)

    else:
        # --- GITLAB ROLLBACK ---
        print("\nMode: GitLab")
        rollback_dir = root / "rollback-temp"
        if rollback_dir.exists():
            shutil.rmtree(rollback_dir)
        rollback_dir.mkdir()

        print("\nDownloading artifacts...")
        download_gitlab_artifacts(rollback_pipeline_id, rollback_dir)

        manifest_path = rollback_dir / "archives" / "ROLLBACK_MANIFEST.yaml"
        if not manifest_path.exists():
            print(f"Error: ROLLBACK_MANIFEST.yaml not found in downloaded artifacts at {manifest_path}")
            sys.exit(1)

        manifest = load_yaml(manifest_path)
        validate_rollback_manifest(manifest, target_server)

        archive_path_str = manifest.get('rollback_bundle_path')
        if not archive_path_str:
            print("Error: 'rollback_bundle_path' not found in manifest.")
            sys.exit(1)

        archive_path = rollback_dir / archive_path_str
        if not archive_path.exists():
            print(f"Error: Rollback bundle ZIP not found at {archive_path}")
            sys.exit(1)
        
        execute_rollback_from_archive(archive_path, target_url, import_script)

    print("=" * 60)
    print("ROLLBACK COMPLETE")
    print("=" * 60)
