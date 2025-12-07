"""MCP Server for RouterOS API access

This MCP server provides access to RouterOS devices through both API and SSH connections.
"""

import asyncio
from typing import Dict, List, Any
import json
import re
import socket

from fastmcp import FastMCP
from .settings import settings, DeviceManager
from .client import RouterOSClient
import routeros_api


# Create MCP server instance
mcp = FastMCP("RouterOS MCP Server")

# Initialize device manager (will be loaded on first access)
_device_manager = None


def get_device_manager() -> DeviceManager:
    """Get or create device manager instance."""
    global _device_manager
    if _device_manager is None:
        config_path = settings.get_devices_config_path()
        _device_manager = DeviceManager(config_path)
    return _device_manager


def load_device_connection(device_name: str) -> Dict[str, Any] | None:
    """Load device connection information"""
    device_manager = get_device_manager()
    device = device_manager.get_device(device_name)
    
    if not device:
        return None
    
    if device.disabled:
        return None
    
    # Use fallback_ip if hostname DNS resolution fails
    hostname = device.hostname
    if device.fallback_ip:
        try:
            socket.gethostbyname(device.hostname)
        except socket.gaierror:
            hostname = device.fallback_ip
    
    return {
        'hostname': hostname,
        'username': device.username,
        'password': device.password,
        'private_key': device.private_key,
        'device': device
    }


def get_api_connection(hostname: str, username: str, password: str, use_ssl: bool = False, port: int = None):
    """Get RouterOS API connection"""
    if port is None:
        port = settings.routeros_api_ssl_port if use_ssl else settings.routeros_api_port
    
    connection = routeros_api.RouterOsApiPool(
        hostname,
        username=username,
        password=password,
        port=port,
        use_ssl=use_ssl,
        ssl_verify=False,
        ssl_verify_hostname=False,
        plaintext_login=True
    )
    return connection


def _format_bytes(bytes_value: Any) -> str:
    """Format bytes to human readable format"""
    try:
        bytes_val = int(bytes_value)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"
    except:
        return str(bytes_value)


# Core functions
def _list_routeros_devices() -> List[Dict[str, Any]]:
    """List all RouterOS devices"""
    device_manager = get_device_manager()
    devices = []
    
    for device in device_manager.list_all_devices():
        devices.append(device.to_dict())
    
    return devices


def _routeros_command(
    device_name: str,
    command: str,
    parameters: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Execute a RouterOS API command on a device"""
    conn_info = load_device_connection(device_name)
    if not conn_info:
        return {'error': f'Device {device_name} not found or disabled'}
    
    try:
        connection = get_api_connection(
            conn_info['hostname'],
            conn_info['username'],
            conn_info['password']
        )
        api = connection.get_api()
        
        # Get the resource path
        resource_path = command
        for operation in ['/print', '/add', '/set', '/remove', '/get']:
            if resource_path.endswith(operation):
                resource_path = resource_path[:-len(operation)]
                break
        
        resource = api.get_resource(resource_path)
        
        # Execute command
        if command.endswith('/print'):
            result = resource.get(**(parameters or {}))
        elif command.endswith('/add'):
            result = resource.add(**(parameters or {}))
        elif command.endswith('/set'):
            result = resource.set(**(parameters or {}))
        elif command.endswith('/remove'):
            result = resource.remove(**(parameters or {}))
        else:
            result = resource.get(**(parameters or {}))
        
        connection.disconnect()
        
        return {
            'success': True,
            'device': device_name,
            'command': command,
            'result': result
        }
        
    except Exception as e:
        return {
            'success': False,
            'device': device_name,
            'command': command,
            'error': str(e)
        }


def _routeros_system_info(device_name: str) -> Dict[str, Any]:
    """Get system information from a RouterOS device"""
    result = _routeros_command(device_name, '/system/resource/print')
    
    if result.get('success') and result.get('result'):
        info = result['result'][0] if isinstance(result['result'], list) else result['result']
        return {
            'success': True,
            'device': device_name,
            'info': {
                'platform': info.get('platform', 'N/A'),
                'board_name': info.get('board-name', 'N/A'),
                'version': info.get('version', 'N/A'),
                'uptime': info.get('uptime', 'N/A'),
                'cpu': info.get('cpu', 'N/A'),
                'cpu_load': f"{info.get('cpu-load', 'N/A')}%",
                'memory_free': _format_bytes(info.get('free-memory', 0)),
                'memory_total': _format_bytes(info.get('total-memory', 0)),
                'storage_free': _format_bytes(info.get('free-hdd-space', 0)),
                'storage_total': _format_bytes(info.get('total-hdd-space', 0))
            }
        }
    
    return result


def _routeros_interfaces(device_name: str, include_disabled: bool = False) -> Dict[str, Any]:
    """List interfaces on a RouterOS device"""
    parameters = {} if include_disabled else {'disabled': 'false'}
    result = _routeros_command(device_name, '/interface/print', parameters)
    
    if result.get('success') and result.get('result'):
        interfaces = []
        for iface in result['result']:
            interfaces.append({
                'name': iface.get('name'),
                'type': iface.get('type'),
                'mac_address': iface.get('mac-address'),
                'disabled': iface.get('disabled', 'false') == 'true',
                'running': iface.get('running', 'false') == 'true',
                'comment': iface.get('comment', '')
            })
        
        return {
            'success': True,
            'device': device_name,
            'interfaces': interfaces
        }
    
    return result


def _routeros_ip_addresses(device_name: str) -> Dict[str, Any]:
    """List IP addresses on a RouterOS device"""
    result = _routeros_command(device_name, '/ip/address/print')
    
    if result.get('success') and result.get('result'):
        addresses = []
        for addr in result['result']:
            addresses.append({
                'address': addr.get('address'),
                'interface': addr.get('interface'),
                'network': addr.get('network'),
                'disabled': addr.get('disabled', 'false') == 'true',
                'dynamic': addr.get('dynamic', 'false') == 'true',
                'comment': addr.get('comment', '')
            })
        
        return {
            'success': True,
            'device': device_name,
            'ip_addresses': addresses
        }
    
    return result


def _routeros_routes(device_name: str, only_active: bool = True) -> Dict[str, Any]:
    """List routes on a RouterOS device"""
    result = _routeros_command(device_name, '/ip/route/print')
    
    if result.get('success') and result.get('result'):
        routes = []
        for route in result['result']:
            if only_active and route.get('active', 'false') != 'true':
                continue
                
            routes.append({
                'dst_address': route.get('dst-address'),
                'gateway': route.get('gateway'),
                'distance': route.get('distance'),
                'scope': route.get('scope'),
                'target_scope': route.get('target-scope'),
                'active': route.get('active', 'false') == 'true',
                'dynamic': route.get('dynamic', 'false') == 'true',
                'static': route.get('static', 'false') == 'true',
                'comment': route.get('comment', '')
            })
        
        return {
            'success': True,
            'device': device_name,
            'routes': routes
        }
    
    return result


def _routeros_neighbors(device_name: str) -> Dict[str, Any]:
    """List discovered neighbors on a RouterOS device"""
    result = _routeros_command(device_name, '/ip/neighbor/print')
    
    if result.get('success') and result.get('result'):
        neighbors = []
        for neighbor in result['result']:
            neighbors.append({
                'interface': neighbor.get('interface'),
                'mac_address': neighbor.get('mac-address'),
                'identity': neighbor.get('identity'),
                'platform': neighbor.get('platform'),
                'version': neighbor.get('version'),
                'ip_address': neighbor.get('address'),
                'uptime': neighbor.get('uptime')
            })
        
        return {
            'success': True,
            'device': device_name,
            'neighbors': neighbors
        }
    
    return result


def _routeros_bridges(device_name: str) -> Dict[str, Any]:
    """List bridges on a RouterOS device"""
    result = _routeros_command(device_name, '/interface/bridge/print')
    
    if result.get('success') and result.get('result'):
        bridges = []
        for bridge in result['result']:
            bridges.append({
                'name': bridge.get('name'),
                'mac_address': bridge.get('mac-address'),
                'disabled': bridge.get('disabled', 'false') == 'true',
                'running': bridge.get('running', 'false') == 'true',
                'mtu': bridge.get('mtu'),
                'arp': bridge.get('arp'),
                'comment': bridge.get('comment', '')
            })
        
        return {
            'success': True,
            'device': device_name,
            'bridges': bridges
        }
    
    return result


def _routeros_logs(device_name: str, topics: List[str] | None = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """Get logs from a RouterOS device with pagination"""
    result = _routeros_command(device_name, '/log/print', {})
    
    if result.get('success') and result.get('result'):
        logs = []
        result_list = result['result'] if isinstance(result['result'], list) else [result['result']]
        
        # Apply client-side filtering if topics specified
        if topics:
            filtered_list = []
            for entry in result_list:
                entry_topics = entry.get('topics', '')
                entry_message = entry.get('message', '')
                
                for pattern in topics:
                    try:
                        if pattern.startswith('^(?!'):
                            combined_text = f"{entry_topics} {entry_message}"
                            if re.search(pattern, combined_text, re.IGNORECASE):
                                filtered_list.append(entry)
                                break
                        else:
                            if (re.search(pattern, entry_topics, re.IGNORECASE) or 
                                re.search(pattern, entry_message, re.IGNORECASE)):
                                filtered_list.append(entry)
                                break
                    except re.error:
                        pattern_lower = pattern.lower()
                        if (pattern_lower in entry_topics.lower() or 
                            pattern_lower in entry_message.lower()):
                            filtered_list.append(entry)
                            break
            result_list = filtered_list
        
        # Reverse to show newest first
        result_list.reverse()
        
        # Apply pagination
        total_filtered = len(result_list)
        start_idx = offset
        end_idx = offset + limit if limit > 0 else total_filtered
        paginated_results = result_list[start_idx:end_idx]
        
        for entry in paginated_results:
            logs.append({
                'time': entry.get('time'),
                'topics': entry.get('topics'),
                'message': entry.get('message')
            })
        
        return {
            'success': True,
            'device': device_name,
            'logs': logs,
            'total_available': total_filtered,
            'total_returned': len(logs),
            'offset': offset,
            'limit': limit
        }
    
    return result


def _routeros_config(device_name: str) -> Dict[str, Any]:
    """Get configuration from a RouterOS device"""
    conn_info = load_device_connection(device_name)
    if not conn_info:
        return {'error': f'Device {device_name} not found or disabled'}
    
    client = RouterOSClient(
        hostname=conn_info['hostname'],
        username=conn_info['username'],
        password=conn_info['password'],
        private_key=conn_info.get('private_key')
    )
    
    success, result = client.export_config()
    
    if success:
        return {
            'success': True,
            'device': device_name,
            'config': result.get('config', '')
        }
    else:
        return {
            'success': False,
            'device': device_name,
            'error': result.get('error', 'Failed to export configuration'),
            'api_error': result.get('api_error'),
            'ssh_error': result.get('ssh_error')
        }


def _routeros_ping(device_name: str, address: str, count: int = 4, size: int | None = None,
                   interval: float | None = None, timeout: int | None = None) -> Dict[str, Any]:
    """Execute ping command on a RouterOS device"""
    conn_info = load_device_connection(device_name)
    if not conn_info:
        return {'error': f'Device {device_name} not found or disabled'}
    
    client = RouterOSClient(
        hostname=conn_info['hostname'],
        username=conn_info['username'],
        password=conn_info['password'],
        private_key=conn_info.get('private_key')
    )
    
    success, result = client.execute_ping(address, count, size, interval, timeout)
    
    if success:
        return {
            'success': True,
            'device': device_name,
            **result
        }
    else:
        return {
            'success': False,
            'device': device_name,
            'target': address,
            'error': result.get('error', 'Ping failed')
        }


# MCP Tool wrappers
@mcp.tool()
def routeros_list_devices() -> List[Dict[str, Any]]:
    """List all RouterOS devices from configuration
    
    Returns:
        List of devices with their connection details
    """
    return _list_routeros_devices()


@mcp.tool()
def routeros_command(
    device_name: str,
    command: str,
    parameters_json: str | None = None
) -> Dict[str, Any]:
    """Execute a RouterOS API command
    
    Args:
        device_name: Device name from configuration
        command: RouterOS API path (e.g., '/system/resource/print')
        parameters_json: JSON string of command parameters
    """
    parameters = json.loads(parameters_json) if parameters_json else None
    return _routeros_command(device_name, command, parameters)


@mcp.tool()
def routeros_system_info(device_name: str) -> Dict[str, Any]:
    """Get system information and resource usage
    
    Args:
        device_name: Device name from configuration
    """
    return _routeros_system_info(device_name)


@mcp.tool()
def routeros_interfaces(device_name: str, include_disabled: bool = False) -> Dict[str, Any]:
    """List network interfaces with status
    
    Args:
        device_name: Device name from configuration
        include_disabled: Include disabled interfaces
    """
    return _routeros_interfaces(device_name, include_disabled)


@mcp.tool()
def routeros_ip_addresses(device_name: str) -> Dict[str, Any]:
    """List IP addresses configured on interfaces
    
    Args:
        device_name: Device name from configuration
    """
    return _routeros_ip_addresses(device_name)


@mcp.tool()
def routeros_ip_routes(device_name: str, only_active: bool = True) -> Dict[str, Any]:
    """List IP routing table entries
    
    Args:
        device_name: Device name from configuration
        only_active: Filter to only active routes
    """
    return _routeros_routes(device_name, only_active)


@mcp.tool()
def routeros_bridges(device_name: str) -> Dict[str, Any]:
    """List Layer 2 bridge configurations
    
    Args:
        device_name: Device name from configuration
    """
    return _routeros_bridges(device_name)


@mcp.tool()
def routeros_neighbors(device_name: str) -> Dict[str, Any]:
    """List discovered network neighbors via CDP/LLDP
    
    Args:
        device_name: Device name from configuration
    """
    return _routeros_neighbors(device_name)


@mcp.tool()
def routeros_logs(device_name: str, topics: str | None = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """Get logs from a RouterOS device with pagination
    
    Args:
        device_name: Device name from configuration
        topics: Comma-separated regex patterns to search for
        limit: Maximum number of log entries to return
        offset: Number of log entries to skip from most recent
    """
    topic_list = None
    if topics:
        topic_list = [t.strip() for t in topics.split(',')]
    
    return _routeros_logs(device_name, topic_list, limit, offset)


@mcp.tool()
def routeros_config(device_name: str) -> Dict[str, Any]:
    """Get full configuration export from device
    
    Args:
        device_name: Device name from configuration
    """
    return _routeros_config(device_name)


@mcp.tool()
def routeros_ping(device_name: str, address: str, count: int = 4, size: int | None = None,
                  interval: float | None = None, timeout: int | None = None) -> Dict[str, Any]:
    """Execute ping from a RouterOS device
    
    Args:
        device_name: Device name from configuration
        address: Target IP or hostname to ping
        count: Number of packets (max: 10)
        size: Packet size in bytes
        interval: Delay between packets in seconds
        timeout: Per-packet timeout in seconds
    """
    return _routeros_ping(device_name, address, count, size, interval, timeout)


# MCP Resources
@mcp.resource("routeros://inventory")
def get_inventory() -> str:
    """RouterOS device inventory"""
    devices = _list_routeros_devices()
    return json.dumps(devices, indent=2)


@mcp.resource("routeros://device/{device_name}/status")
def get_device_status(device_name: str) -> str:
    """Real-time status of a specific RouterOS device"""
    info = _routeros_system_info(device_name)
    return json.dumps(info, indent=2)


@mcp.resource("routeros://device/{device_name}/config")
def get_device_config(device_name: str) -> str:
    """Current configuration of a specific RouterOS device"""
    config = _routeros_config(device_name)
    if config.get('success') and config.get('config'):
        return config['config']
    else:
        return json.dumps({
            'error': config.get('error', 'Failed to retrieve configuration')
        }, indent=2)
