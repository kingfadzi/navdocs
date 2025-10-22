#!/usr/bin/env python3
"""
Storage backend abstraction for PPM deployment bundles.
Supports local storage (mock mode) and S3/MinIO (production mode).
"""

import os
import sys
from pathlib import Path
from datetime import datetime


class StorageBackend:
    """Base interface for storage backends."""

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """Upload bundle from remote server to storage."""
        raise NotImplementedError

    def download_to_server(self, ssh_executor, ssh_config, storage_key, remote_path):
        """Download bundle from storage to remote server."""
        raise NotImplementedError

    def get_metadata(self, storage_key):
        """Get metadata about stored bundle."""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Local storage backend for mock/development mode."""

    def __init__(self, config):
        self.bundle_dir = Path(config.get('bundle_dir', './bundles'))

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """No-op for local mode - files are already local."""
        local_path = self.bundle_dir / Path(remote_path).name
        return {
            'storage_mode': 'local',
            'local_path': str(local_path),
            'bundle_filename': Path(remote_path).name
        }

    def download_to_server(self, ssh_executor, ssh_config, storage_key, remote_path):
        """No-op for local mode - files are already local."""
        return True

    def get_metadata(self, storage_key):
        """Get local file metadata."""
        if isinstance(storage_key, dict):
            local_path = storage_key.get('local_path')
        else:
            local_path = storage_key

        if Path(local_path).exists():
            return {
                'storage_mode': 'local',
                'local_path': local_path,
                'exists': True
            }
        return {'exists': False}


class S3Storage(StorageBackend):
    """S3/MinIO storage backend for production mode."""

    def __init__(self, config):
        self.bucket = config.get('bucket_name')
        self.region = config.get('region', 'us-east-1')
        self.endpoint_url = config.get('endpoint_url')  # None = AWS S3, URL = MinIO
        self.prefix = config.get('prefix', 'bundles/')

        if 'AWS_ACCESS_KEY_ID' not in os.environ:
            print("ERROR: AWS_ACCESS_KEY_ID environment variable not set")
            sys.exit(1)
        if 'AWS_SECRET_ACCESS_KEY' not in os.environ:
            print("ERROR: AWS_SECRET_ACCESS_KEY environment variable not set")
            sys.exit(1)

        self._client = None

    def _get_client(self):
        """Lazy initialization of boto3 client."""
        if self._client is None:
            try:
                import boto3
                from botocore.exceptions import ClientError
                self._client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
                    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
                    region_name=self.region
                )
                self._client_error = ClientError
            except ImportError:
                print("ERROR: boto3 not installed. Install with: pip install boto3")
                sys.exit(1)
        return self._client

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """
        Upload bundle from remote server to S3 by first downloading it to the runner.
        """
        s3_client = self._get_client()
        local_temp_dir = Path('./temp_bundles')
        local_temp_dir.mkdir(exist_ok=True)
        local_path = local_temp_dir / Path(remote_path).name

        # Step 1: Download the file from the remote server to the local runner
        print(f"Downloading {remote_path} from remote server...")
        try:
            ssh_executor.scp_download(ssh_config, remote_path, str(local_path))
            print(f"✓ Downloaded to: {local_path}")
        except Exception as e:
            print(f"ERROR: Failed to download bundle from remote server: {e}")
            sys.exit(1)

        # Step 2: Upload the local file to S3 using boto3
        s3_url = f"s3://{self.bucket}/{storage_key}"
        print(f"Uploading to S3: {s3_url}")
        try:
            s3_client.upload_file(str(local_path), self.bucket, storage_key)
            print(f"✓ Uploaded: {s3_url}\n")
        except Exception as e:
            print(f"ERROR: S3 upload failed: {e}")
            sys.exit(1)
        finally:
            # Clean up the local temporary file
            if os.path.exists(local_path):
                os.remove(local_path)

        return {
            'storage_mode': 's3',
            's3_bucket': self.bucket,
            's3_key': storage_key,
            'bundle_filename': Path(remote_path).name,
            's3_url': s3_url
        }

    def download_to_server(self, ssh_executor, ssh_config, bundle_metadata, remote_path):
        """Download bundle from S3/MinIO to remote server."""
        env = os.environ.copy()

        if isinstance(bundle_metadata, dict):
            s3_key = bundle_metadata.get('s3_key')
            s3_bucket = bundle_metadata.get('s3_bucket', self.bucket)
        else:
            s3_key = bundle_metadata
            s3_bucket = self.bucket

        s3_url = f"s3://{s3_bucket}/{s3_key}"

        aws_cmd = (
            f"AWS_ACCESS_KEY_ID={os.environ['AWS_ACCESS_KEY_ID']} "
            f"AWS_SECRET_ACCESS_KEY={os.environ['AWS_SECRET_ACCESS_KEY']} "
        )

        if self.endpoint_url:
            aws_cmd += f"AWS_ENDPOINT_URL={self.endpoint_url} "

        aws_cmd += f"aws s3 cp {s3_url} {remote_path} --region {self.region}"

        print(f"Downloading from S3: {s3_url}")

        try:
            stdout, stderr, returncode = ssh_executor.ssh_exec(ssh_config, aws_cmd, env)

            if returncode != 0:
                print(f"ERROR: S3 download failed: {stderr}")
                sys.exit(1)

            print(f"✓ Downloaded to: {remote_path}\n")
            return True

        except Exception as e:
            print(f"ERROR: S3 download failed: {e}")
            sys.exit(1)

    def get_metadata(self, storage_key):
        """Get S3 object metadata."""
        s3_client = self._get_client()

        try:
            response = s3_client.head_object(Bucket=self.bucket, Key=storage_key)
            return {
                'storage_mode': 's3',
                's3_bucket': self.bucket,
                's3_key': storage_key,
                'exists': True,
                'size': response.get('ContentLength'),
                'last_modified': response.get('LastModified')
            }
        except self._client_error as e:
            if e.response['Error']['Code'] == '404':
                return {'exists': False}
            raise


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
