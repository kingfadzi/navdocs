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
        ssh_user = ssh_config.get('ssh_user') or os.environ.get('SSH_USER', 'ppm-deploy')
        ssh_port = ssh_config.get('ssh_port') or int(os.environ.get('SSH_PORT', '22'))

        # Derive SSH password variable from env_type: SSH_PASSWORD_{ENV_TYPE}
        env_type = ssh_config.get('env_type', '').upper()
        ssh_password_var = ssh_config.get('ssh_password_var') or f"SSH_PASSWORD_{env_type}"

        if ssh_password_var not in os.environ:
            raise ValueError(f"SSH password not found in environment: {ssh_password_var}")

        if env is None:
            env = os.environ.copy()
        env['SSHPASS'] = os.environ[ssh_password_var]

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
        ssh_user = ssh_config.get('ssh_user') or os.environ.get('SSH_USER', 'ppm-deploy')
        ssh_port = ssh_config.get('ssh_port') or int(os.environ.get('SSH_PORT', '22'))

        return [
            'sshpass', '-e',
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-p', str(ssh_port),
            f'{ssh_user}@{ssh_host}',
            remote_command
        ]


def create_remote_executor():
    """Factory function to create RemoteExecutor instance."""
    return RemoteExecutor()
