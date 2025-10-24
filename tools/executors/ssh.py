#!/usr/bin/env python3
"""
Remote execution helpers for SSH operations.
Provides simple wrappers around sshpass + ssh commands.
"""

import subprocess
import os


class RemoteExecutor:
    """SSH remote executor using sshpass."""

    def _get_credentials(self, ssh_config):
        """Returns (username, password, username_env_name, password_env_name)."""
        ssh_vars = ssh_config.get('ssh_env_vars', {})
        username_env = ssh_vars.get('username')
        password_env = ssh_vars.get('password')

        if not username_env or not password_env:
            raise ValueError(
                f"ERROR: Missing ssh_env_vars in server config.\n"
                f"Add to deployment-config.yaml: ssh_env_vars: {{username: 'ENV_VAR', password: 'ENV_VAR'}}"
            )

        username = os.environ.get(username_env)
        password = os.environ.get(password_env)

        return username, password, username_env, password_env

    def ssh_exec(self, ssh_config, command, env=None):
        """Execute command on remote server via SSH."""
        ssh_host = ssh_config['ssh_host']
        ssh_user, ssh_password, username_env, password_env = self._get_credentials(ssh_config)
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user or not ssh_password:
            raise ValueError(f"SSH credentials not found: {username_env} and {password_env} required")

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
        ssh_user, _, username_env, _ = self._get_credentials(ssh_config)
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user:
            raise ValueError(f"SSH user not found: {username_env} required")

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
        ssh_user, ssh_password, username_env, password_env = self._get_credentials(ssh_config)
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user or not ssh_password:
            raise ValueError(f"SSH credentials not found: {username_env} and {password_env} required")

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

    def scp_upload(self, ssh_config, local_path, remote_path):
        """Upload file to remote server via SCP."""
        ssh_host = ssh_config['ssh_host']
        ssh_user, ssh_password, username_env, password_env = self._get_credentials(ssh_config)
        ssh_port = ssh_config.get('ssh_port', 22)

        if not ssh_user or not ssh_password:
            raise ValueError(f"SSH credentials not found: {username_env} and {password_env} required")

        env = os.environ.copy()
        env['SSHPASS'] = ssh_password

        scp_cmd = [
            'sshpass', '-e',
            'scp',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-P', str(ssh_port),
            local_path,
            f'{ssh_user}@{ssh_host}:{remote_path}'
        ]

        result = subprocess.run(scp_cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"SCP upload failed (exit {result.returncode}): {result.stderr}")

        return result.stdout


def create_remote_executor():
    """Factory function to create RemoteExecutor instance."""
    return RemoteExecutor()
