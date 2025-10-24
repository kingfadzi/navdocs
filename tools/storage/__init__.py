"""
Storage backend abstraction package.

This package provides abstraction for different storage backends
(local filesystem, S3) for deployment artifacts and snapshots.
"""

import sys

from .local import LocalStorage
from .s3 import S3Storage


def get_storage_backend(config):
    """Factory function to get appropriate storage backend."""
    storage_mode = config['deployment'].get('storage_backend', 'local')

    if storage_mode == 'local':
        return LocalStorage(config['deployment'])
    elif storage_mode == 's3':
        return S3Storage(config.get('s3', {}))
    else:
        print(f"ERROR: Unknown storage backend: {storage_mode}")
        sys.exit(1)


__all__ = ['LocalStorage', 'S3Storage', 'get_storage_backend']
