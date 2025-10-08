#!/usr/bin/env python3
"""
PPM Rollback Module
Handles rollback deployments using manifest-based discovery
"""

import yaml
import subprocess
import sys
import os
from pathlib import Path
import zipfile
import shutil


def load_yaml(file_path):
    """Load YAML file and return contents."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def download_gitlab_artifacts_from_pipeline(pipeline_id, output_dir):
    """
    Download ALL artifacts from a GitLab pipeline (manifest-based discovery).

    Instead of searching for specific job names, downloads all artifacts
    and lets the manifest tell us which bundle to use.

    Args:
        pipeline_id: GitLab pipeline ID (integer)
        output_dir: Local directory to extract artifacts

    Returns:
        Path to the extracted artifacts directory

    Uses CI_JOB_TOKEN (in pipeline) or GITLAB_TOKEN (manual) for authentication.
    Works with both GitLab.com and on-prem GitLab (uses CI_API_V4_URL).
    """
    import json

    # Get GitLab credentials
    gitlab_token = os.environ.get('CI_JOB_TOKEN') or os.environ.get('GITLAB_TOKEN')
    if not gitlab_token:
        print("Error: No GitLab authentication found")
        print("Set CI_JOB_TOKEN (automatic in pipeline) or GITLAB_TOKEN (for manual use)")
        sys.exit(1)

    # Get project info from environment
    project_id = os.environ.get('CI_PROJECT_ID')
    gitlab_api_url = os.environ.get('CI_API_V4_URL')

    if not project_id:
        print("Error: CI_PROJECT_ID not set")
        print("When running manually, set: export CI_PROJECT_ID=your_project_id")
        sys.exit(1)

    if not gitlab_api_url:
        print("Error: CI_API_V4_URL not set")
        print()
        print("Set the on-prem GitLab API URL:")
        print("  export CI_API_V4_URL=https://gitlab.lab.com/api/v4")
        print()
        print("Note: This is automatically set in GitLab CI pipelines")
        sys.exit(1)

    print(f"Fetching jobs from pipeline {pipeline_id}...")

    # Get jobs from pipeline
    jobs_url = f"{gitlab_api_url}/projects/{project_id}/pipelines/{pipeline_id}/jobs"

    cmd = [
        'curl', '-sS', '--fail',
        '--header', f'PRIVATE-TOKEN: {gitlab_token}',
        jobs_url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error fetching pipeline jobs:")
        print(result.stderr)
        print()
        print("Tips:")
        print(f"  - Verify pipeline ID {pipeline_id} exists")
        print("  - Check you have access to the project")
        print(f"  - View in GitLab: {gitlab_api_url.replace('/api/v4', '')}/pipelines/{pipeline_id}")
        sys.exit(1)

    # Parse jobs and find job with ROLLBACK_MANIFEST.yaml artifact
    jobs = json.loads(result.stdout)
    manifest_job = None

    for job in jobs:
        # Look for archive jobs (they should have the manifest)
        job_name = job.get('name', '')
        if 'archive' in job_name.lower() and job.get('status') == 'success':
            manifest_job = job
            break

    if not manifest_job:
        print(f"Error: No successful archive job found in pipeline {pipeline_id}")
        print()
        print("The pipeline must have completed with archived artifacts")
        sys.exit(1)

    job_id = manifest_job['id']
    print(f"Found archive job: {manifest_job['name']} (job #{job_id})")

    # Download artifacts ZIP
    artifacts_url = f"{gitlab_api_url}/projects/{project_id}/jobs/{job_id}/artifacts"
    temp_zip = output_dir / "pipeline-artifacts.zip"

    print(f"Downloading artifacts from pipeline {pipeline_id}...")

    cmd = [
        'curl', '-sS', '--fail',
        '--header', f'JOB-TOKEN: {gitlab_token}',
        '--output', str(temp_zip),
        artifacts_url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error downloading artifacts:")
        print(result.stderr)
        print()
        print("Tips:")
        print("  - Check artifact hasn't expired (prod artifacts: 1 year)")
        print("  - Verify the archive job completed successfully")
        sys.exit(1)

    print(f"Downloaded artifacts: {temp_zip}")

    # Extract artifacts
    print(f"Extracting artifacts...")
    with zipfile.ZipFile(temp_zip, 'r') as zipf:
        zipf.extractall(output_dir)

    # Cleanup temp ZIP
    os.remove(temp_zip)

    print(f"Extracted to: {output_dir}")
    return output_dir


def validate_rollback_manifest(manifest, bom_target_server):
    """
    Validate rollback manifest matches current BOM requirements.

    Args:
        manifest: Parsed ROLLBACK_MANIFEST.yaml dict
        bom_target_server: Target server from current BOM

    Raises SystemExit if validation fails
    """
    manifest_target = manifest['deployment_metadata']['target_server']

    print(f"Validating manifest...")
    print(f"  Manifest target: {manifest_target}")
    print(f"  BOM target:      {bom_target_server}")

    if manifest_target != bom_target_server:
        print()
        print("ERROR: Target server mismatch!")
        print()
        print("The rollback archive is for a different environment:")
        print(f"  Archive was deployed to: {manifest_target}")
        print(f"  Current BOM targets:     {bom_target_server}")
        print()
        print("To rollback this environment, use a rollback_pipeline_id that deployed to it.")
        sys.exit(1)

    print(f"  ✓ Target server matches")
    print()


def rollback_local(bom_file, validate_bom_func, run_import_func):
    """
    Rollback deployment using local archive and manifest.

    Uses the local ROLLBACK_MANIFEST.yaml to find and redeploy the archive.
    For local development and testing.

    Args:
        bom_file: Path to BOM file
        validate_bom_func: Function to validate BOM (from deploy.py)
        run_import_func: Function to import bundles (from deploy.py)

    Note: Rollback is atomic - no extract/archive needed.
    """
    # Validate BOM first (mirrors CI pipeline)
    validate_bom_func(bom_file)

    print("=" * 60)
    print("ROLLBACK DEPLOYMENT (Local Mode)")
    print("=" * 60)
    print(f"BOM: {bom_file}")
    print()

    # Get paths
    root = Path(__file__).parent.parent

    # Load BOM
    bom = load_yaml(bom_file)
    target_server = bom['target_server']

    print(f"Target: {target_server}")
    print(f"Mode: Local archive")
    print()

    # Load config
    config = load_yaml(root / "config" / "deployment-config.yaml")
    target_url = config['servers'][target_server]['url']
    import_script = config['kmigrator']['import_script']

    # Read local manifest
    manifest_path = root / "ROLLBACK_MANIFEST.yaml"
    if not manifest_path.exists():
        print("Error: ROLLBACK_MANIFEST.yaml not found in project root")
        print()
        print("Local rollback requires a manifest from a previous local deployment.")
        print()
        print("To create one:")
        print("  1. Run a deployment: python3 tools/deploy.py functional-release --bom <bom>")
        print("  2. This creates: ROLLBACK_MANIFEST.yaml")
        print("  3. Then rollback: python3 tools/deploy.py rollback --bom <bom>")
        sys.exit(1)

    print(f"Found local rollback manifest: ROLLBACK_MANIFEST.yaml")
    manifest = load_yaml(manifest_path)
    print()

    # Validate manifest matches BOM
    validate_rollback_manifest(manifest, target_server)

    # Get rollback bundle path from manifest
    rollback_bundle_path = manifest['rollback_bundle_path']
    archive_path = root / rollback_bundle_path

    if not archive_path.exists():
        print(f"Error: Rollback bundle not found: {rollback_bundle_path}")
        print()
        print("The manifest references a bundle that doesn't exist locally.")
        print(f"Expected: {archive_path}")
        print()
        print("The archive may have been deleted or moved.")
        sys.exit(1)

    print(f"Found rollback bundle: {rollback_bundle_path}")
    print()

    # Display deployment metadata
    metadata = manifest['deployment_metadata']
    print("Deployment metadata:")
    print(f"  Profile:        {metadata['profile']}")
    print(f"  Type:           {metadata['deployment_type']}")
    print(f"  Change Request: {metadata['change_request']}")
    print(f"  Version:        {metadata['bom_version']}")
    print(f"  Entities:       {metadata['entities_count']}")
    print(f"  Extracted:      {metadata['extracted_at']}")
    print()

    # Extract deployment archive
    print("Extracting deployment archive...")
    rollback_dir = root / "rollback-temp"
    rollback_dir.mkdir(exist_ok=True)
    extract_dir = rollback_dir / "deployment-extract"
    extract_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        zipf.extractall(extract_dir)
        print(f"Extracted to: {extract_dir}")
    print()

    # Read flags from archive
    flags_file = extract_dir / "flags.txt"
    with open(flags_file, 'r') as f:
        flags = f.read().strip()

    print(f"Using original deployment flags: {flags}")
    print()

    # Find all bundles in archive
    bundle_dir = extract_dir / "bundles"
    bundles = list(bundle_dir.glob("*.xml"))

    print(f"Found {len(bundles)} bundles to import")
    print()

    # Import all bundles
    for bundle in bundles:
        run_import_func(import_script, target_url, str(bundle), flags, 'charset', 'nochange')
        print()

    # Cleanup
    print("Cleaning up temporary files...")
    shutil.rmtree(rollback_dir)
    print()

    print("=" * 60)
    print(f"ROLLBACK COMPLETE: {len(bundles)} entities restored")
    print("=" * 60)


def rollback_from_gitlab(bom_file, validate_bom_func, run_import_func, rollback_pipeline_id):
    """
    Rollback deployment using GitLab artifacts and manifest.

    Downloads artifacts from GitLab pipeline, reads ROLLBACK_MANIFEST.yaml
    to find the exact bundle, validates target environment, and redeploys.

    Args:
        bom_file: Path to BOM file
        validate_bom_func: Function to validate BOM (from deploy.py)
        run_import_func: Function to import bundles (from deploy.py)
        rollback_pipeline_id: GitLab pipeline ID to rollback from

    Note: Rollback is atomic - no extract/archive needed.
    """
    # Validate BOM first (mirrors CI pipeline)
    validate_bom_func(bom_file)

    print("=" * 60)
    print("ROLLBACK DEPLOYMENT (GitLab Mode)")
    print("=" * 60)
    print(f"BOM: {bom_file}")
    print()

    # Get paths
    root = Path(__file__).parent.parent

    # Load BOM
    bom = load_yaml(bom_file)
    target_server = bom['target_server']

    print(f"Target: {target_server}")
    print(f"Rollback pipeline: #{rollback_pipeline_id}")
    print()

    # Load config
    config = load_yaml(root / "config" / "deployment-config.yaml")
    target_url = config['servers'][target_server]['url']
    import_script = config['kmigrator']['import_script']

    # Download all artifacts from GitLab pipeline
    print("Downloading artifacts from GitLab pipeline...")
    rollback_dir = root / "rollback-temp"
    rollback_dir.mkdir(exist_ok=True)

    download_gitlab_artifacts_from_pipeline(rollback_pipeline_id, rollback_dir)
    print()

    # Find and parse ROLLBACK_MANIFEST.yaml
    manifest_path = rollback_dir / "ROLLBACK_MANIFEST.yaml"
    if not manifest_path.exists():
        print("Error: ROLLBACK_MANIFEST.yaml not found in artifacts")
        print()
        print("This pipeline may have been created before manifest-based rollback was implemented.")
        print("Use a more recent pipeline ID that includes the rollback manifest.")
        shutil.rmtree(rollback_dir)
        sys.exit(1)

    print(f"Found rollback manifest: ROLLBACK_MANIFEST.yaml")
    manifest = load_yaml(manifest_path)
    print()

    # Validate manifest matches BOM
    validate_rollback_manifest(manifest, target_server)

    # Get rollback bundle path from manifest
    rollback_bundle_path = manifest['rollback_bundle_path']
    archive_path = rollback_dir / rollback_bundle_path

    if not archive_path.exists():
        print(f"Error: Rollback bundle not found: {rollback_bundle_path}")
        print()
        print("The manifest references a bundle that doesn't exist in the artifacts.")
        shutil.rmtree(rollback_dir)
        sys.exit(1)

    print(f"Found rollback bundle: {rollback_bundle_path}")
    print()

    # Display deployment metadata
    metadata = manifest['deployment_metadata']
    print("Deployment metadata:")
    print(f"  Profile:        {metadata['profile']}")
    print(f"  Type:           {metadata['deployment_type']}")
    print(f"  Change Request: {metadata['change_request']}")
    print(f"  Version:        {metadata['bom_version']}")
    print(f"  Entities:       {metadata['entities_count']}")
    print(f"  Extracted:      {metadata['extracted_at']}")
    print()

    # Extract deployment archive
    print("Extracting deployment archive...")
    extract_dir = rollback_dir / "deployment-extract"
    extract_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(archive_path, 'r') as zipf:
        zipf.extractall(extract_dir)
        print(f"Extracted to: {extract_dir}")
    print()

    # Read flags from archive
    flags_file = extract_dir / "flags.txt"
    with open(flags_file, 'r') as f:
        flags = f.read().strip()

    print(f"Using original deployment flags: {flags}")
    print()

    # Find all bundles in archive
    bundle_dir = extract_dir / "bundles"
    bundles = list(bundle_dir.glob("*.xml"))

    print(f"Found {len(bundles)} bundles to import")
    print()

    # Import all bundles
    for bundle in bundles:
        run_import_func(import_script, target_url, str(bundle), flags, 'charset', 'nochange')
        print()

    # Cleanup
    print("Cleaning up temporary files...")
    shutil.rmtree(rollback_dir)
    print()

    print("=" * 60)
    print(f"ROLLBACK COMPLETE: {len(bundles)} entities restored")
    print("=" * 60)


def rollback(bom_file, validate_bom_func, run_import_func):
    """
    Rollback deployment router - detects local vs GitLab mode.

    Checks rollback_pipeline_id in BOM:
    - "local" → Uses local archive (for development/testing)
    - numeric → Downloads from GitLab API (for production)

    Args:
        bom_file: Path to BOM file
        validate_bom_func: Function to validate BOM (from deploy.py)
        run_import_func: Function to import bundles (from deploy.py)

    Note: Rollback is atomic - no extract/archive needed.
    """
    # Load BOM to check rollback mode
    bom = load_yaml(bom_file)
    rollback_pipeline_id = bom.get('rollback_pipeline_id')

    if not rollback_pipeline_id:
        print("Error: No rollback_pipeline_id specified in BOM")
        print()
        print("Add the pipeline ID from a previous deployment:")
        print()
        print("For local rollback (development/testing):")
        print("  rollback_pipeline_id: local")
        print()
        print("For GitLab rollback (production):")
        print("  rollback_pipeline_id: 12345  # Pipeline ID from GitLab")
        print()
        print("Find the pipeline ID in GitLab:")
        print("  1. Go to CI/CD → Pipelines")
        print("  2. Find the successful deployment you want to rollback to")
        print("  3. Copy the pipeline ID number (e.g., #12345)")
        sys.exit(1)

    # Route to local or GitLab mode
    if str(rollback_pipeline_id).lower() == 'local':
        # LOCAL MODE: Use local archive
        rollback_local(bom_file, validate_bom_func, run_import_func)
    else:
        # GITLAB MODE: Download from GitLab API
        rollback_from_gitlab(bom_file, validate_bom_func, run_import_func, rollback_pipeline_id)
