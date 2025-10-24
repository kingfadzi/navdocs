#!/usr/bin/env python3
"""
Executor factory and package exports.
"""

from .local import LocalExecutor
from .remote import RemoteKMigratorExecutor
from .ssh import RemoteExecutor
from ..storage import get_storage_backend


def is_remote_mode(server_config, config):
    """Check if we're using remote execution + storage backend."""
    return (
        server_config.get('ssh_host') is not None and
        config['deployment'].get('storage_backend', 'local') != 'local'
    )


def get_executor(config, server_config):
    """
    Factory function to create appropriate executor.

    Args:
        config: Deployment configuration dict
        server_config: Server configuration dict

    Returns:
        LocalExecutor or RemoteKMigratorExecutor instance
    """
    if is_remote_mode(server_config, config):
        # Remote mode: use RemoteKMigratorExecutor with S3 storage
        storage = get_storage_backend(config)
        ssh = RemoteExecutor()
        return RemoteKMigratorExecutor(storage, ssh)
    else:
        # Local mode: use LocalExecutor
        return LocalExecutor()


# Package exports
__all__ = ['LocalExecutor', 'RemoteKMigratorExecutor', 'get_executor', 'is_remote_mode']
