#!/usr/bin/env python3
"""
Base storage backend interface for PPM deployment bundles.
"""


class StorageBackend:
    """Base interface for storage backends."""

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """Upload bundle from remote server to storage."""
        raise NotImplementedError

    def download_to_server(self, ssh_executor, ssh_config, storage_key, remote_path):
        """Download bundle from storage to remote server."""
        raise NotImplementedError

    def get_metadata(self, storage_key):
        """Get metadata about stored bundle."""
        raise NotImplementedError

    def upload_file(self, local_path, storage_key):
        """Upload local file to storage (for archives)."""
        raise NotImplementedError

    def download_file(self, storage_key, local_path):
        """Download file from storage to local path (for rollback)."""
        raise NotImplementedError
