#!/usr/bin/env python3
"""
Local executor for kMigrator operations (mock mode).
"""

import subprocess
import glob
import os

from .base import BaseExecutor
from ..deployment.utils import get_ppm_credentials


class LocalExecutor(BaseExecutor):
    """Local kMigrator executor for testing (uses subprocess)."""

    def extract(self, script_path, url, entity_id, reference_code, server_config=None):
        username, password = get_ppm_credentials(server_config)

        # Build kMigrator command - referenceCode is now MANDATORY per OpenText spec
        cmd = [
            'bash', script_path, '-username', username, '-password', password,
            '-url', url, '-action', 'Bundle', '-entityId', str(entity_id),
            '-referenceCode', reference_code
        ]

        print(f"Extracting entity {entity_id} ({reference_code}) from {url} (LOCAL)")

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
        username, password = get_ppm_credentials(server_config)

        cmd = [
            'bash', script_path, '-username', username, '-password', password,
            '-url', url, '-action', 'import', '-filename', bundle_file,
            '-i18n', i18n, '-refdata', refdata, '-flags', flags
        ]
        print(f"Importing {bundle_file} to {url} (LOCAL)")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
