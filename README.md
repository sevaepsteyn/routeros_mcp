# RouterOS MCP Server

A Model Context Protocol (MCP) server for interacting with MikroTik RouterOS devices. This server provides AI assistants with comprehensive access to RouterOS devices through both API and SSH connections, with automatic fallback mechanisms for reliability.

## Features

- **Multiple Connection Methods**: API (port 8728), API with SSL (port 8729), and SSH (port 22)
- **Automatic Fallback**: Tries connection methods in configurable order until successful
- **Multi-Device Support**: Manage multiple RouterOS devices from a single MCP server
- **Comprehensive Tools**: System info, interfaces, IP addresses, routes, neighbors, bridges, logs, config export, and ping
- **Smart Configuration Export**: Automatically falls back to SSH when API permissions are insufficient
- **DNS Fallback**: Supports fallback IP addresses when DNS resolution fails
- **Flexible Configuration**: YAML-based device configuration with environment variable overrides
- **Type Safety**: Full type hints and pydantic-based settings validation

## Installation

### Using UV (recommended)

```bash
cd routeros_mcp
uv sync
```

### Using pip

```bash
cd routeros_mcp
pip install -e .
```

## Configuration

### Device Configuration

Create a `devices.yaml` file in one of these locations:
- `etc/devices.yaml` (in the package directory)
- Or specify a custom path with `ROUTEROS_DEVICES_CONFIG` environment variable

Example `devices.yaml`:

```yaml
devices:
  - name: core-gw
    hostname: core-gw.example.com
    username: admin
    password: your-password
    disabled: false
    fallback_ip: 10.26.0.1  # Optional: used if DNS fails
    private_key: null        # Optional: SSH private key path

  - name: branch-router
    hostname: 192.168.1.1
    username: admin
    password: another-password
    disabled: false
    fallback_ip: null
    private_key: null
```

See `etc/devices.yaml.example` for a complete example.

### Environment Variables (Optional)

Create a `.env` file to customize connection settings:

```env
# RouterOS connection settings (defaults shown)
ROUTEROS_API_PORT=8728
ROUTEROS_API_SSL_PORT=8729
ROUTEROS_SSH_PORT=22
ROUTEROS_TIMEOUT=10
ROUTEROS_CONNECTION_ORDER=api,api_ssl,ssh

# Path to devices.yaml
ROUTEROS_DEVICES_CONFIG=/path/to/devices.yaml

# Logging level
ROUTEROS_LOG_LEVEL=INFO
```

See `.env.example` for all available options.

## Usage

### Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "routeros": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/routeros-mcp",
        "run",
        "routeros-mcp"
      ]
    }
  }
}
```

See `etc/claude_desktop_config_example.json` for more options.

### Command Line

```bash
# With UV
uv run routeros-mcp

# With Python
python -m routeros_mcp
```

## Available Tools

### Device Management

- `routeros_list_devices()` - List all configured RouterOS devices
- `routeros_system_info(device_name)` - Get system information (CPU, memory, uptime, version, etc.)

### Network Information

- `routeros_interfaces(device_name, include_disabled)` - List network interfaces with status
- `routeros_ip_addresses(device_name)` - List IP addresses configured on interfaces
- `routeros_ip_routes(device_name, only_active)` - List routing table entries
- `routeros_neighbors(device_name)` - List discovered neighbors (CDP/LLDP)
- `routeros_bridges(device_name)` - List Layer 2 bridge configurations

### Monitoring

- `routeros_logs(device_name, topics, limit, offset)` - Get device logs with pagination and filtering

### Configuration & Diagnostics

- `routeros_config(device_name)` - Get full configuration export (with automatic SSH fallback)
- `routeros_ping(device_name, address, count, size, interval, timeout)` - Execute ping from device

### Advanced

- `routeros_command(device_name, command, parameters_json)` - Execute any RouterOS API command

## Tool Examples

### List Devices

```
Tool: routeros_list_devices
Returns: [{"name": "core-gw", "hostname": "192.168.1.1", ...}]
```

### Get System Information

```
Tool: routeros_system_info
Parameters:
  - device_name: "core-gw"
Returns: {"success": true, "info": {"version": "7.12", "uptime": "2w3d", ...}}
```

### Get Filtered Logs

```
Tool: routeros_logs
Parameters:
  - device_name: "core-gw"
  - topics: "ospf,error"  # Comma-separated regex patterns
  - limit: 20
  - offset: 0
Returns: {"logs": [...], "total_available": 150, "total_returned": 20}
```

### Execute Custom API Command

```
Tool: routeros_command
Parameters:
  - device_name: "core-gw"
  - command: "/ip/firewall/filter/print"
  - parameters_json: "{}"
Returns: {"success": true, "result": [...]}
```

### Ping from Router

```
Tool: routeros_ping
Parameters:
  - device_name: "core-gw"
  - address: "8.8.8.8"
  - count: 5
Returns: {"results": [...], "summary": {"sent": 5, "received": 5, "packet_loss_percent": 0}}
```

## Available Resources

- `routeros://inventory` - Real-time device inventory
- `routeros://device/{device_name}/status` - Live device status
- `routeros://device/{device_name}/config` - Current device configuration

## Connection Methods

The server tries connection methods in the order specified by `ROUTEROS_CONNECTION_ORDER` (default: api, api_ssl, ssh):

1. **API (port 8728)**: RouterOS API v2 without SSL - fastest method
2. **API SSL (port 8729)**: RouterOS API v2 with SSL encryption
3. **SSH (port 22)**: Fallback method using SSH commands

### Notes on Permissions

- **Read-only API access**: Most tools work with read-only API permissions
- **Configuration export**: Requires read-write API permissions OR falls back to SSH automatically
- **Ping**: Always uses SSH (not available via API)

## Security Considerations

- Store `devices.yaml` securely as it contains passwords
- `devices.yaml` is in `.gitignore` by default
- Consider using environment variables for sensitive data in production
- API connections use plaintext authentication (required for RouterOS 6.43+)
- SSL verification is disabled for API SSL connections (common for self-signed certs)

## Troubleshooting

### Device Not Found

- Check that device name matches exactly in `devices.yaml`
- Ensure device is not marked as `disabled: true`
- Verify `devices.yaml` is in a searched location

### Connection Failures

- Verify hostname/IP is reachable: `ping <hostname>`
- Check RouterOS API is enabled: `/ip service print` (look for api/api-ssl)
- Verify SSH is enabled: `/ip ssh print`
- Test credentials manually
- Check firewall rules allow connections on required ports
- Review server logs for detailed error messages

### Configuration Export Fails

- Requires read-write API permissions OR SSH access
- Server automatically falls back to SSH if API fails
- Check that user has `/export` command permissions

### DNS Resolution Issues

- Use `fallback_ip` in device configuration
- Server automatically uses fallback IP if DNS fails

## Development

### Project Structure

```
routeros-mcp/
├── pyproject.toml
├── README.md
├── LICENSE
├── .env.example
├── .gitignore
├── etc/
│   ├── claude_desktop_config_example.json
│   └── devices.yaml.example
└── src/
    └── routeros_mcp/
        ├── __init__.py
        ├── __main__.py        # Entry point
        ├── server.py          # MCP server and tools
        ├── client.py          # RouterOS API/SSH client
        ├── settings.py        # Configuration management
        └── exceptions.py      # Custom exceptions
```

### Running Tests

```bash
# Install development dependencies
uv sync --dev

# Run tests (if available)
pytest

# Type checking
mypy src/routeros_mcp
```

### Adding New Tools

1. Add the core function to `server.py` (e.g., `_routeros_new_feature()`)
2. Add MCP tool wrapper with `@mcp.tool()` decorator
3. Add comprehensive docstring with parameter descriptions
4. Update README.md with examples

## RouterOS API Reference

Common API command paths (use with `routeros_command`):

- `/system/resource/print` - System resources
- `/interface/print` - Network interfaces
- `/ip/address/print` - IP addresses
- `/ip/route/print` - Routing table
- `/ip/firewall/filter/print` - Firewall rules
- `/ip/firewall/nat/print` - NAT rules
- `/routing/ospf/neighbor/print` - OSPF neighbors
- `/routing/bgp/peer/print` - BGP peers
- `/system/identity/print` - System identity
- `/system/clock/print` - System time
- `/log/print` - System logs

For complete API documentation, see: https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Support

- RouterOS Documentation: https://help.mikrotik.com/docs/spaces/ROS/
- RouterOS API Documentation: https://help.mikrotik.com/docs/spaces/ROS/pages/47579160/API
- MCP Documentation: https://modelcontextprotocol.io/

## Changelog

### 0.1.0 (Initial Release)

- Multi-device support with YAML configuration
- API, API SSL, and SSH connection methods
- Automatic fallback mechanisms
- Comprehensive RouterOS tools and resources
- Environment-based configuration
- Full type safety with pydantic
