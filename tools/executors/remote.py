#!/usr/bin/env python3
"""
Remote executor for kMigrator operations with S3 storage.
"""

import os
from datetime import datetime

from .base import BaseExecutor
from .ssh import RemoteExecutor
from ..deployment.utils import get_ppm_credentials


class RemoteKMigratorExecutor(BaseExecutor):
    """
    Remote kMigrator executor with S3 storage.

    Executes kMigrator on remote PPM servers via SSH.
    Bundles are uploaded to S3 for storage.
    Used in production environments.
    """

    def __init__(self, storage, ssh_executor=None):
        """
        Initialize remote executor.

        Args:
            storage: Storage backend instance (S3Storage)
            ssh_executor: RemoteExecutor instance (optional, creates new if None)
        """
        self.storage = storage
        self.ssh = ssh_executor if ssh_executor else RemoteExecutor()

    def _get_remote_workspace(self):
        """Generate remote workspace directory path."""
        pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
        return f"/tmp/ppm-bundles-{pipeline_id}"

    def _setup_remote_workspace(self, server_config):
        """Create remote workspace directory."""
        remote_dir = self._get_remote_workspace()
        self.ssh.ssh_exec_check(server_config, f"mkdir -p {remote_dir}")
        return remote_dir

    def _cleanup_remote_workspace(self, server_config):
        """Cleanup remote workspace directory."""
        remote_dir = self._get_remote_workspace()
        self.ssh.ssh_exec(server_config, f"rm -rf {remote_dir}")

    def _execute_kmigrator(self, server_config, kmigrator_cmd, operation="operation"):
        """Execute kMigrator command and handle errors."""
        print(f"Executing kMigrator {operation}...")
        stdout, stderr, returncode = self.ssh.ssh_exec(server_config, kmigrator_cmd)

        if returncode != 0:
            raise RuntimeError(f"kMigrator {operation} failed: {stderr}")

        print(stdout)
        return stdout

    def extract(self, script_path, url, entity_id, reference_code=None, server_config=None):
        """Extract entity remotely and download to local bundles/ directory."""
        username, password = get_ppm_credentials(server_config)

        # Generate paths
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        ref_suffix = f"_{reference_code}" if reference_code else ""
        bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}{ref_suffix}_{timestamp}.xml"

        from pathlib import Path
        local_bundle_dir = Path("./bundles")
        local_bundle_dir.mkdir(exist_ok=True)
        local_bundle_file = local_bundle_dir / bundle_filename

        ref_info = f" ({reference_code})" if reference_code else " (ALL)"
        print(f"Extracting entity {entity_id}{ref_info} from {url} (REMOTE)")

        try:
            remote_bundle_dir = self._setup_remote_workspace(server_config)
            remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"

            # Build and execute kMigrator command
            kmigrator_cmd = (
                f"{script_path} -username {username} -password {password} "
                f"-url {url} -action Bundle -entityId {entity_id}"
            )
            if reference_code:
                kmigrator_cmd += f" -referenceCode {reference_code}"
            kmigrator_cmd += f" -filename {remote_bundle_file}"

            self._execute_kmigrator(server_config, kmigrator_cmd, "extract")

            # Download bundle
            print(f"Downloading to local: {local_bundle_file}")
            self.ssh.scp_download(server_config, remote_bundle_file, str(local_bundle_file))
            print(f"✓ Downloaded: {local_bundle_file}")

            self._cleanup_remote_workspace(server_config)
            return str(local_bundle_file)

        except Exception as e:
            print(f"ERROR: Remote extraction failed: {e}")
            self._cleanup_remote_workspace(server_config)
            raise

    def import_bundle(self, script_path, url, bundle_file, flags, i18n, refdata, server_config=None):
        """Import bundle from local file (GitLab artifact) to remote server."""
        username, password = get_ppm_credentials(server_config)

        from pathlib import Path
        bundle_filename = Path(bundle_file).name

        print(f"Importing {bundle_filename} to {url} (REMOTE)")

        try:
            remote_bundle_dir = self._setup_remote_workspace(server_config)
            remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"

            # Upload bundle to remote
            print(f"Uploading to remote server...")
            self.ssh.scp_upload(server_config, bundle_file, remote_bundle_file)

            # Execute kMigrator import
            kmigrator_cmd = (
                f"{script_path} -username {username} -password {password} "
                f"-url {url} -action import -filename {remote_bundle_file} "
                f"-i18n {i18n} -refdata {refdata} -flags {flags}"
            )

            self._execute_kmigrator(server_config, kmigrator_cmd, "import")
            self._cleanup_remote_workspace(server_config)

        except Exception as e:
            print(f"ERROR: Remote import failed: {e}")
            self._cleanup_remote_workspace(server_config)
            raise
