#!/usr/bin/env python3
"""
Remote execution helpers for SSH operations.
Provides simple wrappers around sshpass + ssh commands.
"""

import subprocess
import os


class RemoteExecutor:
    """SSH remote executor using sshpass."""

    def ssh_exec(self, ssh_config, command, env=None):
        """Execute command on remote server via SSH."""
        ssh_host = ssh_config['ssh_host']
        ssh_user = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
        ssh_password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user or not ssh_password:
            raise ValueError("SSH credentials not found: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD required")

        if env is None:
            env = os.environ.copy()
        env['SSHPASS'] = ssh_password

        ssh_cmd = [
            'sshpass', '-e',
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-p', str(ssh_port),
            f'{ssh_user}@{ssh_host}',
            command
        ]

        result = subprocess.run(ssh_cmd, env=env, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode

    def ssh_exec_check(self, ssh_config, command, env=None):
        """Execute command and raise error if it fails."""
        stdout, stderr, returncode = self.ssh_exec(ssh_config, command, env)

        if returncode != 0:
            raise RuntimeError(f"SSH command failed (exit {returncode}): {stderr}")

        return stdout

    def ssh_exec_multi(self, ssh_config, commands, env=None):
        """Execute multiple commands in one SSH session (joined with &&)."""
        combined_command = ' && '.join(commands)
        return self.ssh_exec(ssh_config, combined_command, env)

    def build_ssh_cmd(self, ssh_config, remote_command):
        """Build sshpass + ssh command list."""
        ssh_host = ssh_config['ssh_host']
        ssh_user = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user:
            raise ValueError("SSH user not found: PPM_SERVICE_ACCOUNT_USER required")

        return [
            'sshpass', '-e',
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-p', str(ssh_port),
            f'{ssh_user}@{ssh_host}',
            remote_command
        ]

    def scp_download(self, ssh_config, remote_path, local_path):
        """Download file from remote server via SCP."""
        ssh_host = ssh_config['ssh_host']
        ssh_user = os.environ.get('PPM_SERVICE_ACCOUNT_USER')
        ssh_password = os.environ.get('PPM_SERVICE_ACCOUNT_PASSWORD')
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user or not ssh_password:
            raise ValueError("SSH credentials not found: PPM_SERVICE_ACCOUNT_USER and PPM_SERVICE_ACCOUNT_PASSWORD required")

        env = os.environ.copy()
        env['SSHPASS'] = ssh_password

        scp_cmd = [
            'sshpass', '-e',
            'scp',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-P', str(ssh_port),
            f'{ssh_user}@{ssh_host}:{remote_path}',
            local_path
        ]

        result = subprocess.run(scp_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"SCP download failed (exit {result.returncode}): {result.stderr}")

        return result.stdout


def create_remote_executor():
    """Factory function to create RemoteExecutor instance."""
    return RemoteExecutor()
