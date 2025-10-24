#!/usr/bin/env python3
"""
Local storage backend for mock/development mode.
"""

from pathlib import Path

from .base import StorageBackend


class LocalStorage(StorageBackend):
    """Local storage backend for mock/development mode."""

    def __init__(self, config):
        self.bundle_dir = Path(config.get('bundle_dir', './bundles'))

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """No-op for local mode - files are already local."""
        local_path = self.bundle_dir / Path(remote_path).name
        return {
            'storage_mode': 'local',
            'local_path': str(local_path),
            'bundle_filename': Path(remote_path).name
        }

    def download_to_server(self, ssh_executor, ssh_config, storage_key, remote_path):
        """No-op for local mode - files are already local."""
        return True

    def get_metadata(self, storage_key):
        """Get local file metadata."""
        if isinstance(storage_key, dict):
            local_path = storage_key.get('local_path')
        else:
            local_path = storage_key

        if Path(local_path).exists():
            return {
                'storage_mode': 'local',
                'local_path': local_path,
                'exists': True
            }
        return {'exists': False}

    def upload_file(self, local_path, storage_key):
        """No-op for local mode - file already exists locally."""
        return str(local_path)

    def download_file(self, storage_key, local_path):
        """No-op for local mode - file already exists locally."""
        return str(storage_key)
