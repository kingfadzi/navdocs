#!/usr/bin/env python3
"""S3 storage backend for production mode."""

import os
import sys
from pathlib import Path

from .base import StorageBackend


class S3Storage(StorageBackend):
    """S3 storage backend for production mode."""

    def __init__(self, config):
        self.bucket = config.get('bucket_name')
        self.region = config.get('region', 'us-east-1')
        self.endpoint_url = config.get('endpoint_url')
        self.prefix = config.get('prefix', 'bundles/')

        self._validate_credentials()
        self._client = None

    def _validate_credentials(self):
        """Validate required AWS credentials are set."""
        missing = []
        if 'AWS_ACCESS_KEY_ID' not in os.environ:
            missing.append('AWS_ACCESS_KEY_ID')
        if 'AWS_SECRET_ACCESS_KEY' not in os.environ:
            missing.append('AWS_SECRET_ACCESS_KEY')

        if missing:
            print(f"ERROR: Missing environment variables: {', '.join(missing)}")
            sys.exit(1)

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
        return f"s3://{bucket or self.bucket}/{storage_key}"

    def _setup_temp_dir(self):
        temp_dir = Path('./temp_bundles')
        temp_dir.mkdir(exist_ok=True)
        return temp_dir

    def _cleanup_temp_file(self, local_path):
        """Remove temporary file if it exists."""
        if os.path.exists(local_path):
            os.remove(local_path)

    def _handle_error(self, operation, error):
        """Unified error handling."""
        print(f"ERROR: {operation} failed: {error}")
        sys.exit(1)

    def _s3_upload(self, local_path, storage_key):
        s3_client = self._get_client()
        s3_url = self._get_s3_url(storage_key)
        print(f"Uploading to S3: {s3_url}")
        try:
            s3_client.upload_file(str(local_path), self.bucket, storage_key)
            print("[OK] Uploaded")
            return s3_url
        except Exception as e:
            self._handle_error("S3 upload", e)

    def _s3_download(self, storage_key, local_path, bucket=None):
        s3_client = self._get_client()
        s3_url = self._get_s3_url(storage_key, bucket)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading from S3: {s3_url}")
        try:
            s3_client.download_file(bucket or self.bucket, storage_key, str(local_path))
            print("[OK] Downloaded")
            return str(local_path)
        except Exception as e:
            self._handle_error("S3 download", e)

    def upload_from_server(self, ssh_executor, ssh_config, remote_path, storage_key):
        """Upload bundle from remote server to S3 via local runner."""
        local_temp_dir = self._setup_temp_dir()
        local_path = local_temp_dir / Path(remote_path).name

        print(f"Downloading {remote_path} from remote...")
        try:
            ssh_executor.scp_download(ssh_config, remote_path, str(local_path))
            print("[OK] Downloaded")
        except Exception as e:
            self._handle_error("Remote download", e)

        s3_url = self._s3_upload(local_path, storage_key)
        self._cleanup_temp_file(local_path)

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

        print("Uploading to remote server...")
        try:
            ssh_executor.scp_upload(ssh_config, str(local_path), remote_path)
            print("[OK] Uploaded to remote")
        except Exception as e:
            self._handle_error("Remote upload", e)
        finally:
            self._cleanup_temp_file(local_path)

        return True

    def get_metadata(self, storage_key):
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
        return self._s3_upload(local_path, storage_key)

    def download_file(self, storage_key, local_path):
        return self._s3_download(storage_key, local_path)
