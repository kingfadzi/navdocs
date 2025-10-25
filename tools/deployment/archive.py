#!/usr/bin/env python3
"""
Archive operations for PPM deployments.
Handles creation of rollback archives, evidence packages, and S3 snapshots.
"""

import yaml
import zipfile
import shutil
import os
from pathlib import Path
from datetime import datetime

from .utils import load_yaml
from ..storage import get_storage_backend


def create_evidence_package(bom_file, archive_path, config):
    """
    Create evidence package for compliance/audit.
    """
    root = Path(__file__).parent.parent.parent
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
    Bundles are always local file paths (from GitLab artifacts).
    """
    root = Path(__file__).parent.parent.parent
    archive_dir = root / config['deployment']['archive_dir']
    archive_dir.mkdir(exist_ok=True)
    bom = load_yaml(bom_file)
    version = bom.get('version', 'unknown')
    change_request = bom.get('change_request', 'baseline')
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    archive_name = f"{change_request}-v{version}-{timestamp}-bundles.zip"
    archive_path = archive_dir / archive_name
    print(f"Creating deployment archive from GitLab artifacts: {archive_name}")

    bundle_filenames = []

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for bundle_path in bundles:
            # Bundles are always local paths (from GitLab artifacts)
            local_path = Path(bundle_path)
            bundle_filename = local_path.name
            zipf.write(local_path, arcname=f"bundles/{bundle_filename}")
            bundle_filenames.append(bundle_filename)

        zipf.write(bom_file, arcname="bom.yaml")
        zipf.writestr("flags.txt", flags)
        manifest = {
            'version': version, 'change_request': change_request,
            'archived_at': datetime.now().isoformat(),
            'bundles': bundle_filenames, 'flags': flags
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


def _setup_snapshot_dir(root, pipeline_id):
    """Setup and return snapshot directory."""
    snapshot_dir = root / "snapshot-temp" / str(pipeline_id)
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    return snapshot_dir


def _copy_bundles_to_snapshot(snapshot_dir, metadata, deployment_type, root):
    """Copy bundles and metadata to snapshot directory."""
    bundles_dir = snapshot_dir / "bundles"
    bundles_dir.mkdir(exist_ok=True)

    for bundle_path in metadata['bundles']:
        bundle_file = Path(bundle_path)
        if bundle_file.exists():
            shutil.copy(bundle_file, bundles_dir / bundle_file.name)
            print(f"Copied bundle: {bundle_file.name}")

    metadata_file = root / f"bundles/{deployment_type}-metadata.yaml"
    if metadata_file.exists():
        shutil.copy(metadata_file, bundles_dir / f"{deployment_type}-metadata.yaml")
        print(f"Copied metadata: {deployment_type}-metadata.yaml")


def _copy_artifacts_to_snapshot(snapshot_dir, archive_path, evidence_path, bom_file, root):
    """Copy archives, evidence, BOM, and rollback manifest to snapshot."""
    # Copy archive
    archives_dir = snapshot_dir / "archives"
    archives_dir.mkdir(exist_ok=True)
    if archive_path.exists():
        shutil.copy(archive_path, archives_dir / archive_path.name)
        print(f"Copied archive: {archive_path.name}")

    # Copy evidence
    evidence_dir = snapshot_dir / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    if evidence_path.exists():
        shutil.copy(evidence_path, evidence_dir / evidence_path.name)
        print(f"Copied evidence: {evidence_path.name}")

    # Copy BOM
    shutil.copy(bom_file, snapshot_dir / "bom.yaml")
    print(f"Copied BOM: {Path(bom_file).name}")

    # Copy ROLLBACK_MANIFEST if exists
    rollback_manifest = root / "archives" / "ROLLBACK_MANIFEST.yaml"
    if rollback_manifest.exists():
        shutil.copy(rollback_manifest, archives_dir / "ROLLBACK_MANIFEST.yaml")
        print("Copied ROLLBACK_MANIFEST for S3 fallback")


def _create_snapshot_manifest(snapshot_dir, pipeline_id, deployment_type, metadata):
    """Create and save snapshot manifest."""
    bundles_dir = snapshot_dir / "bundles"
    archives_dir = snapshot_dir / "archives"
    evidence_dir = snapshot_dir / "evidence"

    snapshot_manifest = {
        'snapshot_version': '1.0.0',
        'created_at': datetime.now().isoformat(),
        'pipeline_id': pipeline_id,
        'deployment_type': deployment_type,
        'snapshot_contents': {
            'bundles': [bundle_file.name for bundle_file in bundles_dir.glob('*.xml')],
            'metadata': [metadata_file.name for metadata_file in bundles_dir.glob('*.yaml')],
            'archives': [archive_file.name for archive_file in archives_dir.glob('*')],
            'evidence': [evidence_file.name for evidence_file in evidence_dir.glob('*.zip')],
            'bom': 'bom.yaml'
        },
        'note': 'Job logs available in GitLab pipeline history',
        'git_context': {
            'commit_sha': os.environ.get('CI_COMMIT_SHA', 'local'),
            'branch': os.environ.get('CI_COMMIT_BRANCH', 'unknown'),
            'commit_message': os.environ.get('CI_COMMIT_MESSAGE', '')
        },
        'deployment_metadata': {
            'deployment_type': metadata.get('deployment_type'),
            'profile': metadata.get('profile'),
            'target_server': metadata.get('target_server'),
            'bom_version': metadata.get('bom_version'),
            'change_request': metadata.get('change_request'),
            'flags': metadata.get('flags')
        }
    }

    manifest_path = snapshot_dir / "SNAPSHOT_MANIFEST.yaml"
    with open(manifest_path, 'w') as f:
        yaml.dump(snapshot_manifest, f, default_flow_style=False, sort_keys=False)
    print(f"Created SNAPSHOT_MANIFEST")


def _upload_snapshot_to_s3(snapshot_dir, pipeline_id, config):
    """Upload snapshot to S3 and cleanup."""
    storage_mode = config['deployment'].get('storage_backend', 'local')

    if storage_mode != 's3':
        print(f"\nLocal mode: Snapshot at {snapshot_dir}")
        return None

    storage = get_storage_backend(config)
    s3_prefix = f"snapshots/{pipeline_id}"
    bucket = config['s3']['bucket_name']

    print(f"\nUploading to S3: s3://{bucket}/{s3_prefix}/")

    uploaded_count = 0
    for file_path in snapshot_dir.rglob('*'):
        if file_path.is_file():
            relative_path = file_path.relative_to(snapshot_dir)
            s3_key = f"{s3_prefix}/{relative_path}"
            storage.upload_file(file_path, s3_key)
            uploaded_count += 1

    s3_snapshot_url = f"s3://{bucket}/{s3_prefix}/"
    print(f"[OK] Uploaded {uploaded_count} files to {s3_snapshot_url}")

    shutil.rmtree(snapshot_dir)
    print("Cleaned up temporary directory")
    return s3_snapshot_url


def create_complete_snapshot(pipeline_id, deployment_type, metadata, bom_file, archive_path, evidence_path, config):
    """Create complete deployment snapshot and upload to S3."""
    root = Path(__file__).parent.parent.parent

    print(f"\n=== CREATING SNAPSHOT (Pipeline {pipeline_id}) ===\n")

    snapshot_dir = _setup_snapshot_dir(root, pipeline_id)
    _copy_bundles_to_snapshot(snapshot_dir, metadata, deployment_type, root)
    _copy_artifacts_to_snapshot(snapshot_dir, archive_path, evidence_path, bom_file, root)
    _create_snapshot_manifest(snapshot_dir, pipeline_id, deployment_type, metadata)
    s3_snapshot_url = _upload_snapshot_to_s3(snapshot_dir, pipeline_id, config)

    print("="*60)
    return s3_snapshot_url


def create_rollback_manifest(archive_location, storage_mode, metadata, bom_file, s3_snapshot_url=None):
    """Create ROLLBACK_MANIFEST.yaml with GitLab + S3 paths."""
    root = Path(__file__).parent.parent.parent
    archive_dir = root / "archives"
    archive_dir.mkdir(exist_ok=True)
    manifest_path = archive_dir / "ROLLBACK_MANIFEST.yaml"

    pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')

    # Rollback archive path (relative to GitLab artifacts root)
    if isinstance(archive_location, Path):
        rollback_bundle_path = f"archives/{archive_location.name}"
    else:
        # Shouldn't happen in new design, but handle for safety
        rollback_bundle_path = str(archive_location)

    # S3 archive URL (within snapshot)
    s3_archive_url = None
    if s3_snapshot_url:
        archive_filename = archive_location.name if isinstance(archive_location, Path) else Path(archive_location).name
        s3_archive_url = f"{s3_snapshot_url}archives/{archive_filename}"

    manifest = {
        'rollback_source': 'gitlab',  # Primary source
        'rollback_bundle_path': rollback_bundle_path,  # GitLab artifact path
        's3_snapshot_url': s3_snapshot_url,  # S3 complete snapshot
        's3_archive_url': s3_archive_url,  # Direct S3 archive path
        'storage_backend': storage_mode,
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
            'pipeline_id': pipeline_id,
            'branch': os.environ.get('CI_COMMIT_BRANCH', 'unknown')
        },
        'manifest_version': '2.0.0',  # Updated version
        'created_at': datetime.now().isoformat()
    }

    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

    print(f"Created rollback manifest: {manifest_path}")
    print(f"Rollback source: GitLab artifacts (fallback: S3)")
    if s3_archive_url:
        print(f"S3 archive: {s3_archive_url}")
