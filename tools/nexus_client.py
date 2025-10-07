#!/usr/bin/env python3
"""
Mock Nexus Client - Simulates artifact upload/download with local file operations
No HTTP - just copies files to/from a local 'nexus-storage' directory
"""

import os
import shutil
from pathlib import Path


def get_nexus_storage_dir():
    """
    Get the local directory that simulates Nexus storage.
    Returns path to nexus-storage/ directory.
    """
    root = Path(__file__).parent.parent
    storage_dir = root / "nexus-storage"
    storage_dir.mkdir(exist_ok=True)
    return storage_dir


def upload_artifact(nexus_url, repository, artifact_path, local_file):
    """
    Mock upload: Copy file to nexus-storage directory.

    Args:
        nexus_url: Ignored (for compatibility)
        repository: Repository name (e.g., "ppm-deployments")
        artifact_path: Path in repository (e.g., "2025/CR-12345.zip")
        local_file: Local file to upload
    """
    # Build storage path
    storage_dir = get_nexus_storage_dir()
    artifact_full_path = storage_dir / repository / artifact_path
    artifact_full_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Uploading to mock Nexus: {repository}/{artifact_path}")

    # Copy file to storage
    shutil.copy2(local_file, artifact_full_path)

    print(f"✓ Upload successful")

    # Return mock URL
    return f"nexus://{repository}/{artifact_path}"


def download_artifact(artifact_url, destination):
    """
    Mock download: Copy file from nexus-storage directory.

    Args:
        artifact_url: URL in format "nexus://repository/path/to/file.zip"
        destination: Local file path to save to

    Returns:
        Path to downloaded file
    """
    # Parse nexus:// URL
    if not artifact_url.startswith('nexus://'):
        raise ValueError(f"Invalid artifact URL: {artifact_url}")

    # Extract repository and path
    parts = artifact_url.replace('nexus://', '').split('/', 1)
    repository = parts[0]
    artifact_path = parts[1]

    print(f"Downloading from mock Nexus: {repository}/{artifact_path}")

    # Find file in storage
    storage_dir = get_nexus_storage_dir()
    artifact_full_path = storage_dir / repository / artifact_path

    if not artifact_full_path.exists():
        raise FileNotFoundError(f"Artifact not found in Nexus: {artifact_url}")

    # Copy from storage to destination
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(artifact_full_path, destination)

    print(f"✓ Downloaded to: {destination}")
    return destination
