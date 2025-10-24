#!/usr/bin/env python3
"""
Base executor interface for kMigrator operations.
"""


class BaseExecutor:
    """Interface for kMigrator executors (local mock or remote production)."""

    def extract(self, script_path, url, entity_id, reference_code=None, server_config=None):
        """Returns local file path or S3 metadata dict."""
        raise NotImplementedError("Subclasses must implement extract()")

    def import_bundle(self, script_path, url, bundle_metadata, flags, i18n, refdata, server_config=None):
        """bundle_metadata can be local file path (string) or S3 metadata (dict)."""
        raise NotImplementedError("Subclasses must implement import_bundle()")
