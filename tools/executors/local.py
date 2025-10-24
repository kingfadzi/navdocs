#!/usr/bin/env python3
"""
Local executor for kMigrator operations (mock mode).
"""

import subprocess
import glob
import os

# Import utilities - handle both direct execution and package import
try:
    from executors.base import BaseExecutor
except ImportError:
    from tools.executors.base import BaseExecutor

try:
    from deployment.utils import get_ppm_credentials
except ImportError:
    from tools.deployment.utils import get_ppm_credentials


class LocalExecutor(BaseExecutor):
    """
    Local kMigrator executor (mock mode).

    Executes kMigrator scripts locally using subprocess.
    Used for testing and development with mock scripts.
    """

    def extract(self, script_path, url, entity_id, reference_code=None, server_config=None):
        """
        Extract entity locally (mock mode).

        Args:
            script_path: Path to kMigrator extract script
            url: PPM server URL
            entity_id: Entity ID to extract
            reference_code: Optional reference code for specific entity
            server_config: Optional server configuration dict (for credential resolution)

        Returns:
            Local file path to extracted bundle
        """
        username, password = get_ppm_credentials(server_config)

        cmd = [
            'bash', script_path, '-username', username, '-password', password,
            '-url', url, '-action', 'Bundle', '-entityId', str(entity_id)
        ]
        if reference_code:
            cmd.extend(['-referenceCode', reference_code])

        ref_info = f" ({reference_code})" if reference_code else " (ALL)"
        print(f"Extracting entity {entity_id}{ref_info} from {url} (LOCAL)")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)

        # Parse output for bundle path
        for line in result.stdout.split('\n'):
            if 'Bundle saved to:' in line:
                return line.split('Bundle saved to:')[1].strip()

        # Fallback: find most recent bundle file
        pattern = f"./bundles/KMIGRATOR_EXTRACT_{entity_id}_*.xml"
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
        return files[0] if files else None

    def import_bundle(self, script_path, url, bundle_file, flags, i18n, refdata, server_config=None):
        """
        Import bundle locally (mock mode).

        Args:
            script_path: Path to kMigrator import script
            url: PPM server URL
            bundle_file: Local file path to bundle
            flags: 25-character kMigrator flag string
            i18n: i18n mode (e.g., 'charset', 'none')
            refdata: Reference data mode (e.g., 'nochange')
            server_config: Optional server configuration dict (for credential resolution)

        Returns:
            None (prints output)
        """
        username, password = get_ppm_credentials(server_config)

        cmd = [
            'bash', script_path, '-username', username, '-password', password,
            '-url', url, '-action', 'import', '-filename', bundle_file,
            '-i18n', i18n, '-refdata', refdata, '-flags', flags
        ]
        print(f"Importing {bundle_file} to {url} (LOCAL)")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
