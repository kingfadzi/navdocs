#!/usr/bin/env python3
"""
Remote executor for kMigrator operations with S3 storage.
"""

import os
from datetime import datetime

# Import utilities - handle both direct execution and package import
try:
    from executors.base import BaseExecutor
    from deploy_utils import get_credentials
    from remote_executor import RemoteExecutor
except ImportError:
    from tools.executors.base import BaseExecutor
    from tools.deploy_utils import get_credentials
    from tools.remote_executor import RemoteExecutor


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

    def extract(self, script_path, url, entity_id, reference_code, server_config):
        """
        Extract entity remotely and upload to storage.

        Args:
            script_path: Path to kMigrator extract script on remote server
            url: PPM server URL
            entity_id: Entity ID to extract
            reference_code: Reference code for specific entity (required for remote)
            server_config: Server configuration dict with ssh_host

        Returns:
            S3 metadata dict with bundle_filename, s3_key, s3_bucket
        """
        username, password = get_credentials()

        # Generate bundle filename
        pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        if reference_code:
            bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}_{reference_code}_{timestamp}.xml"
        else:
            bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}_{timestamp}.xml"

        remote_bundle_dir = f"/tmp/ppm-bundles-{pipeline_id}"
        remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"
        storage_key = f"bundles/{pipeline_id}/{bundle_filename}"

        ssh_host = server_config['ssh_host']

        print(f"Extracting entity {entity_id}" + (f" ({reference_code})" if reference_code else " (ALL)") + f" from {url} (REMOTE → S3)")
        print(f"Remote: {username}@{ssh_host}")

        try:
            # Step 1: Create remote directory
            self.ssh.ssh_exec_check(server_config, f"mkdir -p {remote_bundle_dir}")

            # Step 2: Build and execute kMigrator command
            kmigrator_cmd = (
                f"{script_path} -username {username} -password {password} "
                f"-url {url} -action Bundle -entityId {entity_id}"
            )
            if reference_code:
                kmigrator_cmd += f" -referenceCode {reference_code}"
            kmigrator_cmd += f" -filename {remote_bundle_file}"

            print(f"Executing kMigrator...\n")
            stdout, stderr, returncode = self.ssh.ssh_exec(server_config, kmigrator_cmd)

            if returncode != 0:
                print(f"ERROR: kMigrator extract failed: {stderr}")
                raise RuntimeError(f"kMigrator extract failed: {stderr}")

            print(stdout)

            # Step 3: Upload to storage
            bundle_metadata = self.storage.upload_from_server(
                self.ssh, server_config, remote_bundle_file, storage_key
            )

            # Step 4: Cleanup remote directory
            self.ssh.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")

            return bundle_metadata

        except Exception as e:
            print(f"ERROR: Remote extraction failed: {e}")
            # Cleanup on error
            self.ssh.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")
            raise

    def import_bundle(self, script_path, url, bundle_metadata, flags, i18n, refdata, server_config):
        """
        Import bundle from storage to remote server.

        Args:
            script_path: Path to kMigrator import script on remote server
            url: PPM server URL
            bundle_metadata: S3 metadata dict with bundle_filename, s3_key, etc.
            flags: 25-character kMigrator flag string
            i18n: i18n mode (e.g., 'charset', 'none')
            refdata: Reference data mode (e.g., 'nochange')
            server_config: Server configuration dict with ssh_host

        Returns:
            None (prints output)
        """
        username, password = get_credentials()

        # Extract bundle info from metadata
        bundle_filename = bundle_metadata.get('bundle_filename')

        # Generate remote paths
        pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
        remote_bundle_dir = f"/tmp/ppm-bundles-{pipeline_id}"
        remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"

        ssh_host = server_config['ssh_host']

        print(f"Importing {bundle_filename} to {url} (S3 → REMOTE)")
        print(f"Remote: {username}@{ssh_host}")

        try:
            # Step 1: Create remote directory
            self.ssh.ssh_exec_check(server_config, f"mkdir -p {remote_bundle_dir}")

            # Step 2: Download bundle from storage to remote server
            self.storage.download_to_server(self.ssh, server_config, bundle_metadata, remote_bundle_file)

            # Step 3: Execute kMigrator import
            kmigrator_cmd = (
                f"{script_path} -username {username} -password {password} "
                f"-url {url} -action import -filename {remote_bundle_file} "
                f"-i18n {i18n} -refdata {refdata} -flags {flags}"
            )

            print(f"Executing kMigrator import...\n")
            stdout, stderr, returncode = self.ssh.ssh_exec(server_config, kmigrator_cmd)

            if returncode != 0:
                print(f"ERROR: kMigrator import failed: {stderr}")
                raise RuntimeError(f"kMigrator import failed: {stderr}")

            print(stdout)

            # Step 4: Cleanup remote directory
            self.ssh.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")

        except Exception as e:
            print(f"ERROR: Remote import failed: {e}")
            # Cleanup on error
            self.ssh.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")
            raise
