#!/usr/bin/env python3
"""
Base executor interface for kMigrator operations.
"""


class BaseExecutor:
    """
    Base interface for kMigrator executors.

    Executors handle the actual extraction and import of PPM entities.
    Different implementations support local execution (mock) and remote execution (production).
    """

    def extract(self, script_path, url, entity_id, reference_code=None, server_config=None):
        """
        Extract entity from PPM server.

        Args:
            script_path: Path to kMigrator extract script
            url: PPM server URL
            entity_id: Entity ID to extract
            reference_code: Optional reference code for specific entity
            server_config: Optional server configuration dict (for credential resolution)

        Returns:
            Local file path (LocalExecutor) or S3 metadata dict (RemoteKMigratorExecutor)
        """
        raise NotImplementedError("Subclasses must implement extract()")

    def import_bundle(self, script_path, url, bundle_metadata, flags, i18n, refdata, server_config=None):
        """
        Import bundle to PPM server.

        Args:
            script_path: Path to kMigrator import script
            url: PPM server URL
            bundle_metadata: Local file path (string) or S3 metadata (dict)
            flags: 25-character kMigrator flag string
            i18n: i18n mode (e.g., 'charset', 'none')
            refdata: Reference data mode (e.g., 'nochange')
            server_config: Optional server configuration dict (for credential resolution)

        Returns:
            None (prints output)
        """
        raise NotImplementedError("Subclasses must implement import_bundle()")
