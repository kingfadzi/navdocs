#!/usr/bin/env python3
"""
Base executor interface for kMigrator operations.
"""


class BaseExecutor:
    """Interface for kMigrator executors (local mock or remote production)."""

    def extract(self, script_path, url, entity_id, reference_code, server_config=None):
        """
        Extract entity from PPM server.

        Args:
            script_path: Path to kMigratorExtract.sh
            url: PPM server URL
            entity_id: Entity type ID (e.g., 9 for Workflow)
            reference_code: Entity reference code (MANDATORY per OpenText spec)
            server_config: Server configuration dict

        Returns:
            Local file path to extracted bundle
        """
        raise NotImplementedError("Subclasses must implement extract()")

    def import_bundle(self, script_path, url, bundle_metadata, flags, i18n, refdata, server_config=None):
        """bundle_metadata can be local file path (string) or S3 metadata (dict)."""
        raise NotImplementedError("Subclasses must implement import_bundle()")
