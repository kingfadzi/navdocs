#!/usr/bin/env python3
"""
Remote executor for kMigrator operations with S3 storage.
"""

import os
from datetime import datetime

# Import utilities - handle both direct execution and package import
try:
    from executors.base import BaseExecutor
    from executors.ssh import RemoteExecutor
except ImportError:
    from tools.executors.base import BaseExecutor
    from tools.executors.ssh import RemoteExecutor

try:
    from deployment.utils import get_ppm_credentials
except ImportError:
    from tools.deployment.utils import get_ppm_credentials


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

    def extract(self, script_path, url, entity_id, reference_code=None, server_config=None):
        """
        Extract entity remotely and download to local bundles/ directory.

        Args:
            script_path: Path to kMigrator extract script on remote server
            url: PPM server URL
            entity_id: Entity ID to extract
            reference_code: Reference code for specific entity (optional)
            server_config: Server configuration dict with ssh_host (required for remote)

        Returns:
            Local file path to extracted bundle (for GitLab artifacts)
        """
        username, password = get_ppm_credentials(server_config)

        # Generate bundle filename
        pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        if reference_code:
            bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}_{reference_code}_{timestamp}.xml"
        else:
            bundle_filename = f"KMIGRATOR_EXTRACT_{entity_id}_{timestamp}.xml"

        remote_bundle_dir = f"/tmp/ppm-bundles-{pipeline_id}"
        remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"

        # Local bundles directory (for GitLab artifacts)
        from pathlib import Path
        local_bundle_dir = Path("./bundles")
        local_bundle_dir.mkdir(exist_ok=True)
        local_bundle_file = local_bundle_dir / bundle_filename

        ssh_host = server_config['ssh_host']

        print(f"Extracting entity {entity_id}" + (f" ({reference_code})" if reference_code else " (ALL)") + f" from {url} (REMOTE → LOCAL)")
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

            # Step 3: Download bundle from remote server to local (for GitLab artifacts)
            print(f"Downloading bundle to local: {local_bundle_file}")
            self.ssh.scp_download(server_config, remote_bundle_file, str(local_bundle_file))
            print(f"✓ Downloaded: {local_bundle_file}\n")

            # Step 4: Cleanup remote directory
            self.ssh.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")

            return str(local_bundle_file)

        except Exception as e:
            print(f"ERROR: Remote extraction failed: {e}")
            # Cleanup on error
            self.ssh.ssh_exec(server_config, f"rm -rf {remote_bundle_dir}")
            raise

    def import_bundle(self, script_path, url, bundle_file, flags, i18n, refdata, server_config=None):
        """
        Import bundle from local file (GitLab artifact) to remote server.

        Args:
            script_path: Path to kMigrator import script on remote server
            url: PPM server URL
            bundle_file: Local file path to bundle (from GitLab artifacts)
            flags: 25-character kMigrator flag string
            i18n: i18n mode (e.g., 'charset', 'none')
            refdata: Reference data mode (e.g., 'nochange')
            server_config: Server configuration dict with ssh_host (required for remote)

        Returns:
            None (prints output)
        """
        username, password = get_ppm_credentials(server_config)

        # Get bundle filename from local path
        from pathlib import Path
        bundle_filename = Path(bundle_file).name

        # Generate remote paths
        pipeline_id = os.environ.get('CI_PIPELINE_ID', 'local')
        remote_bundle_dir = f"/tmp/ppm-bundles-{pipeline_id}"
        remote_bundle_file = f"{remote_bundle_dir}/{bundle_filename}"

        ssh_host = server_config['ssh_host']

        print(f"Importing {bundle_filename} to {url} (GITLAB ARTIFACT → REMOTE)")
        print(f"Remote: {username}@{ssh_host}")

        try:
            # Step 1: Create remote directory
            self.ssh.ssh_exec_check(server_config, f"mkdir -p {remote_bundle_dir}")

            # Step 2: Upload bundle from local (GitLab artifact) to remote server
            print(f"Uploading bundle to remote server...")
            self.ssh.scp_upload(server_config, bundle_file, remote_bundle_file)

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
