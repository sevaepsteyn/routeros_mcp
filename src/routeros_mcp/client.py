"""RouterOS client for API and SSH connections."""

import socket
import paramiko
import re
from typing import Dict, Optional, Any, Tuple
import routeros_api

from .settings import settings


class RouterOSClient:
    """Client for interacting with RouterOS devices via API and SSH."""

    def __init__(self, hostname: str, username: str, password: str,
                 private_key: Optional[str] = None):
        """Initialize RouterOS client.

        Args:
            hostname: RouterOS device hostname or IP
            username: Authentication username
            password: Authentication password
            private_key: Optional SSH private key for key-based auth
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.private_key = private_key

    def get_system_resources(self, verbose: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """Get system resources from RouterOS device.

        Tries connection methods in order specified by settings:
        - api: RouterOS API without SSL
        - api_ssl: RouterOS API with SSL
        - ssh: SSH connection as fallback

        Returns:
            Tuple of (success, data_or_error)
        """
        connection_order = settings.routeros_connection_order
        errors = []

        for method in connection_order:
            if method == 'api_ssl':
                result = self._try_api_ssl()
            elif method == 'api':
                result = self._try_api()
            elif method == 'ssh':
                result = self._try_ssh()
            else:
                continue

            if result[0]:  # Success
                return result
            else:
                errors.append(f"{method}: {result[1].get('error', 'Unknown error')}")

        # All methods failed
        return False, {"error": "All connection methods failed", "details": errors}

    def _try_api_ssl(self) -> Tuple[bool, Dict[str, Any]]:
        """Try to connect using API with SSL."""
        try:
            port = settings.routeros_api_ssl_port

            connection = routeros_api.RouterOsApiPool(
                self.hostname,
                username=self.username,
                password=self.password,
                port=port,
                use_ssl=True,
                ssl_verify=False,
                ssl_verify_hostname=False,
                plaintext_login=True
            )
            api = connection.get_api()

            resources = api.get_resource('/system/resource').get()
            connection.disconnect()

            if resources and len(resources) > 0:
                return True, self._parse_resources(resources[0])
            else:
                return False, {"error": "No data returned from API SSL"}

        except Exception as e:
            return False, {"error": f"API SSL failed: {str(e)}"}

    def _try_api(self) -> Tuple[bool, Dict[str, Any]]:
        """Try to connect using API without SSL."""
        try:
            port = settings.routeros_api_port

            connection = routeros_api.RouterOsApiPool(
                self.hostname,
                username=self.username,
                password=self.password,
                port=port,
                use_ssl=False,
                plaintext_login=True
            )
            api = connection.get_api()

            resources = api.get_resource('/system/resource').get()
            connection.disconnect()

            if resources and len(resources) > 0:
                return True, self._parse_resources(resources[0])
            else:
                return False, {"error": "No data returned from API"}

        except Exception as e:
            return False, {"error": f"API failed: {str(e)}"}

    def _try_ssh(self) -> Tuple[bool, Dict[str, Any]]:
        """Try to connect using SSH as fallback."""
        try:
            port = settings.routeros_ssh_port
            timeout = settings.routeros_timeout

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                self.hostname,
                port=port,
                username=self.username,
                password=self.password,
                timeout=timeout,
                look_for_keys=False,
                allow_agent=False
            )

            stdin, stdout, stderr = ssh.exec_command('/system resource print')
            output = stdout.read().decode('utf-8')
            ssh.close()

            if output:
                return True, self._parse_ssh_resources(output)
            else:
                return False, {"error": "No output from SSH command"}

        except Exception as e:
            return False, {"error": f"SSH failed: {str(e)}"}

    def _parse_resources(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Parse resources from API response."""
        return {
            'uptime': resources.get('uptime', 'N/A'),
            'version': resources.get('version', 'N/A'),
            'cpu': resources.get('cpu', 'N/A'),
            'cpu_load': resources.get('cpu-load', 'N/A'),
            'free_memory': self._format_bytes(resources.get('free-memory', 0)),
            'total_memory': self._format_bytes(resources.get('total-memory', 0)),
            'free_hdd_space': self._format_bytes(resources.get('free-hdd-space', 0)),
            'total_hdd_space': self._format_bytes(resources.get('total-hdd-space', 0)),
            'architecture': resources.get('architecture', 'N/A'),
            'board_name': resources.get('board-name', 'N/A'),
            'platform': resources.get('platform', 'N/A')
        }

    def _parse_ssh_resources(self, output: str) -> Dict[str, Any]:
        """Parse resources from SSH output."""
        result = {}

        for line in output.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if 'uptime' in key:
                    result['uptime'] = value
                elif 'version' in key:
                    result['version'] = value
                elif 'cpu' in key and 'load' not in key:
                    result['cpu'] = value
                elif 'cpu-load' in key:
                    result['cpu_load'] = value
                elif 'free-memory' in key:
                    result['free_memory'] = value
                elif 'total-memory' in key:
                    result['total_memory'] = value
                elif 'free-hdd-space' in key:
                    result['free_hdd_space'] = value
                elif 'total-hdd-space' in key:
                    result['total_hdd_space'] = value
                elif 'architecture' in key:
                    result['architecture'] = value
                elif 'board-name' in key:
                    result['board_name'] = value
                elif 'platform' in key:
                    result['platform'] = value

        return result

    def _format_bytes(self, bytes_value: Any) -> str:
        """Format bytes to human readable format."""
        try:
            bytes_val = int(bytes_value)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.1f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.1f} PB"
        except:
            return str(bytes_value)

    def export_config(self) -> Tuple[bool, Dict[str, Any]]:
        """Export device configuration using /export command.

        Tries API first (requires read-write permissions), then falls back to SSH.

        Returns:
            Tuple of (success, data_or_error)
        """
        # Try API first
        api_result = self._try_api_export()
        if api_result[0]:
            return api_result

        # Fallback to SSH
        ssh_result = self._try_ssh_export()
        if ssh_result[0]:
            return ssh_result

        # Both failed
        return False, {
            "error": "Failed to export configuration",
            "api_error": api_result[1].get('error', 'Unknown API error'),
            "ssh_error": ssh_result[1].get('error', 'Unknown SSH error')
        }

    def _try_api_export(self) -> Tuple[bool, Dict[str, Any]]:
        """Try to export configuration using API."""
        # Try SSL first
        try:
            port = settings.routeros_api_ssl_port
            use_ssl = True

            connection = routeros_api.RouterOsApiPool(
                self.hostname,
                username=self.username,
                password=self.password,
                port=port,
                use_ssl=use_ssl,
                ssl_verify=False,
                ssl_verify_hostname=False,
                plaintext_login=True
            )

            api = connection.get_api()
            resource = api.get_resource('/')
            result = resource.call('export', {'verbose': '', 'terse': ''})
            connection.disconnect()

            if result and result.get('ret'):
                return True, {"config": result['ret']}
            else:
                return False, {"error": "Export returned empty data (may require read-write permissions)"}

        except Exception as ssl_error:
            # If SSL fails, try without SSL
            if 'SSL' in str(ssl_error) or 'ssl' in str(ssl_error) or 'handshake' in str(ssl_error):
                try:
                    port = settings.routeros_api_port
                    use_ssl = False

                    connection = routeros_api.RouterOsApiPool(
                        self.hostname,
                        username=self.username,
                        password=self.password,
                        port=port,
                        use_ssl=use_ssl,
                        plaintext_login=True
                    )

                    api = connection.get_api()
                    resource = api.get_resource('/')
                    result = resource.call('export', {'terse': ''})
                    connection.disconnect()

                    if result and result.get('ret'):
                        return True, {"config": result['ret']}
                    else:
                        return False, {"error": "Export returned empty data (may require read-write permissions)"}

                except Exception as e:
                    return False, {"error": f"API export failed: {str(e)}"}
            else:
                return False, {"error": f"API export failed: {str(ssl_error)}"}

    def _try_ssh_export(self) -> Tuple[bool, Dict[str, Any]]:
        """Try to export configuration using SSH."""
        try:
            port = settings.routeros_ssh_port
            timeout = settings.routeros_timeout * 3  # Longer timeout for export

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                self.hostname,
                port=port,
                username=self.username,
                password=self.password,
                timeout=timeout,
                look_for_keys=False,
                allow_agent=False
            )

            stdin, stdout, stderr = ssh.exec_command('/export verbose terse', timeout=timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            error_output = stderr.read().decode('utf-8', errors='ignore')
            ssh.close()

            if output and not error_output:
                clean_output = self._clean_ssh_output(output)
                return True, {"config": clean_output}
            elif error_output:
                return False, {"error": f"SSH export error: {error_output}"}
            else:
                return False, {"error": "No output from SSH export command"}

        except Exception as e:
            return False, {"error": f"SSH export failed: {str(e)}"}

    def _clean_ssh_output(self, output: str) -> str:
        """Clean SSH output by removing terminal control characters."""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        output = ansi_escape.sub('', output)

        # Remove carriage returns and normalize line endings
        output = output.replace('\r\n', '\n').replace('\r', '\n')

        # Remove any leading/trailing whitespace
        output = output.strip()

        return output

    def execute_ping(self, address: str, count: int = 4, size: int | None = None,
                     interval: float | None = None, timeout: int | None = None) -> Tuple[bool, Dict[str, Any]]:
        """Execute ping command on RouterOS device via SSH.

        Args:
            address: Target IP address or hostname
            count: Number of pings (default: 4, max: 10)
            size: Packet size in bytes (optional)
            interval: Time between packets in seconds (optional)
            timeout: Timeout for each packet in seconds (optional)

        Returns:
            Tuple of (success, result_dict)
        """
        # Limit count to prevent timeouts
        count = min(count, 10)

        try:
            port = settings.routeros_ssh_port
            ssh_timeout = settings.routeros_timeout * 3

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                self.hostname,
                port=port,
                username=self.username,
                password=self.password,
                timeout=ssh_timeout,
                look_for_keys=False,
                allow_agent=False
            )

            # Build ping command
            cmd = f"/tool/ping address={address} count={count}"
            if size:
                cmd += f" size={size}"
            if interval:
                cmd += f" interval={interval}"
            if timeout:
                cmd += f" timeout={timeout}"

            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=ssh_timeout)
            output = stdout.read().decode('utf-8', errors='ignore')
            error_output = stderr.read().decode('utf-8', errors='ignore')
            ssh.close()

            if error_output:
                return False, {"error": f"Ping command error: {error_output}"}

            if not output:
                return False, {"error": "No output from ping command"}

            return self._parse_ping_output(output, address)

        except Exception as e:
            return False, {"error": f"SSH ping failed: {str(e)}"}

    def _parse_ping_output(self, output: str, address: str) -> Tuple[bool, Dict[str, Any]]:
        """Parse RouterOS ping output into structured format."""
        lines = output.strip().split('\n')
        results = []
        summary = {"sent": 0, "received": 0, "packet_loss_percent": 0.0}

        for line in lines:
            line = line.strip()
            # Skip empty lines and header
            if not line or "SEQ" in line or "HOST" in line:
                continue

            # Parse ping result line
            parts = line.split()
            if len(parts) >= 5 and parts[0].isdigit():
                try:
                    seq = int(parts[0])
                    host = parts[1]
                    pkt_size = int(parts[2]) if parts[2].isdigit() else 0
                    ttl = int(parts[3]) if parts[3].isdigit() else 0
                    time_str = parts[4] if len(parts) > 4 else ""

                    # Check for timeout
                    if "timeout" in line.lower():
                        results.append({
                            "seq": seq,
                            "host": host,
                            "status": "timeout"
                        })
                        summary["sent"] += 1
                    else:
                        # Parse time (e.g., "4ms141us")
                        time_match = re.search(r'(\d+)ms', time_str)
                        time_ms = int(time_match.group(1)) if time_match else 0

                        results.append({
                            "seq": seq,
                            "host": host,
                            "size": pkt_size,
                            "ttl": ttl,
                            "time_ms": time_ms,
                            "time_str": time_str,
                            "status": "reply"
                        })
                        summary["sent"] += 1
                        summary["received"] += 1

                except (ValueError, IndexError):
                    pass

            # Look for summary line
            elif "sent=" in line or "packet-loss=" in line:
                sent_match = re.search(r'sent=(\d+)', line)
                recv_match = re.search(r'received=(\d+)', line)
                loss_match = re.search(r'packet-loss=([\d.]+)%', line)

                if sent_match:
                    summary["sent"] = int(sent_match.group(1))
                if recv_match:
                    summary["received"] = int(recv_match.group(1))
                if loss_match:
                    summary["packet_loss_percent"] = float(loss_match.group(1))

        # Calculate packet loss if not in output
        if summary["sent"] > 0 and "packet_loss_percent" not in summary:
            loss = ((summary["sent"] - summary["received"]) / summary["sent"]) * 100
            summary["packet_loss_percent"] = round(loss, 2)

        return True, {
            "target": address,
            "results": results,
            "summary": summary,
            "raw_output": output
        }
