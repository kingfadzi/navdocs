#!/usr/bin/env python3
"""
S3/MinIO storage backend for production mode.
"""

import os
import sys
from pathlib import Path

try:
    from .base import StorageBackend
except ImportError:
    from tools.storage.base import StorageBackend


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

    def _get_s3_url(self, storage_key, bucket=None):
        """Format S3 URL."""
        return f"s3://{bucket or self.bucket}/{storage_key}"

    def _setup_temp_dir(self):
        """Create and return temp directory."""
        temp_dir = Path('./temp_bundles')
        temp_dir.mkdir(exist_ok=True)
        return temp_dir

    def _s3_upload(self, local_path, storage_key):
        """Upload file to S3 with error handling."""
        s3_client = self._get_client()
        s3_url = self._get_s3_url(storage_key)
        print(f"Uploading to S3: {s3_url}")
        try:
            s3_client.upload_file(str(local_path), self.bucket, storage_key)
            print(f"✓ Uploaded")
            return s3_url
        except Exception as e:
            print(f"ERROR: S3 upload failed: {e}")
            sys.exit(1)

    def _s3_download(self, storage_key, local_path, bucket=None):
        """Download file from S3 with error handling."""
        s3_client = self._get_client()
        s3_url = self._get_s3_url(storage_key, bucket)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading from S3: {s3_url}")
        try:
            s3_client.download_file(bucket or self.bucket, storage_key, str(local_path))
            print(f"✓ Downloaded")
            return str(local_path)
        except Exception as e:
            print(f"ERROR: S3 download failed: {e}")
            sys.exit(1)

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """Upload bundle from remote server to S3 via local runner."""
        local_temp_dir = self._setup_temp_dir()
        local_path = local_temp_dir / Path(remote_path).name

        print(f"Downloading {remote_path} from remote...")
        try:
            ssh_executor.scp_download(ssh_config, remote_path, str(local_path))
            print(f"✓ Downloaded")
        except Exception as e:
            print(f"ERROR: Failed to download from remote: {e}")
            sys.exit(1)

        s3_url = self._s3_upload(local_path, storage_key)

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
        """Download bundle from S3 to remote server via local runner."""
        local_temp_dir = self._setup_temp_dir()

        if isinstance(bundle_metadata, dict):
            s3_key = bundle_metadata.get('s3_key')
            s3_bucket = bundle_metadata.get('s3_bucket', self.bucket)
            bundle_filename = bundle_metadata.get('bundle_filename', Path(s3_key).name)
        else:
            s3_key = bundle_metadata
            s3_bucket = self.bucket
            bundle_filename = Path(s3_key).name

        local_path = local_temp_dir / bundle_filename

        self._s3_download(s3_key, local_path, s3_bucket)

        print(f"Uploading to remote server...")
        try:
            ssh_executor.scp_upload(ssh_config, str(local_path), remote_path)
            print(f"✓ Uploaded to remote")
        except Exception as e:
            print(f"ERROR: Failed to upload to remote: {e}")
            sys.exit(1)
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)

        return True

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

    def upload_file(self, local_path, storage_key):
        """Upload local file directly to S3."""
        return self._s3_upload(local_path, storage_key)

    def download_file(self, storage_key, local_path):
        """Download file from S3 to local path."""
        return self._s3_download(storage_key, local_path)
