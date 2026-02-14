"""Configuration settings for RouterOS MCP server."""

from typing import Literal, Optional, List, Dict, Any
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import yaml
import os


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # RouterOS connection settings
    routeros_api_port: int = Field(
        8728,
        description="RouterOS API port (non-SSL)",
        alias="ROUTEROS_API_PORT"
    )

    routeros_api_ssl_port: int = Field(
        8729,
        description="RouterOS API port (SSL)",
        alias="ROUTEROS_API_SSL_PORT"
    )

    routeros_ssh_port: int = Field(
        22,
        description="RouterOS SSH port",
        alias="ROUTEROS_SSH_PORT"
    )

    routeros_timeout: int = Field(
        10,
        description="Connection timeout in seconds",
        alias="ROUTEROS_TIMEOUT"
    )

    routeros_connection_order: List[str] = Field(
        ["api", "api_ssl", "ssh"],
        description="Connection method priority order",
        alias="ROUTEROS_CONNECTION_ORDER"
    )

    # Device configuration
    devices_config_path: Optional[str] = Field(
        None,
        description="Path to devices.yaml file",
        alias="ROUTEROS_DEVICES_CONFIG"
    )

    # Server settings
    transport: Literal["stdio", "sse", "streamable-http"] = Field(
        "stdio",
        description="MCP transport type",
        alias="ROUTEROS_TRANSPORT"
    )

    # Logging settings
    log_level: str = Field(
        "INFO",
        description="Logging level",
        alias="ROUTEROS_LOG_LEVEL"
    )

    @field_validator("routeros_connection_order", mode="before")
    @classmethod
    def validate_connection_order(cls, v):
        """Validate connection order list."""
        if isinstance(v, str):
            # Allow comma-separated string
            return [method.strip() for method in v.split(",")]
        return v

    def get_devices_config_path(self) -> Path:
        """Get the resolved path to devices.yaml."""
        if self.devices_config_path:
            return Path(self.devices_config_path)

        # Use etc/ directory relative to package location
        package_dir = Path(__file__).parent.parent.parent
        return package_dir / 'etc' / 'devices.yaml'


class DeviceConfig:
    """Device configuration loaded from YAML."""

    def __init__(self, data: Dict[str, Any]):
        self.name = data['name']
        self.hostname = data['hostname']
        self.username = data['username']
        self.password = data['password']
        self.disabled = data.get('disabled', False)
        self.fallback_ip = data.get('fallback_ip')
        self.private_key = data.get('private_key')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'hostname': self.hostname,
            'username': self.username,
            'disabled': self.disabled,
            'fallback_ip': self.fallback_ip,
            'has_private_key': bool(self.private_key)
        }


class DeviceManager:
    """Manages device configurations from YAML file."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.devices: Dict[str, DeviceConfig] = {}
        self._load_devices()

    def _load_devices(self):
        """Load devices from YAML file."""
        if not self.config_path.exists():
            # Create example config
            self._create_example_config()
            raise FileNotFoundError(
                f"Device configuration not found at {self.config_path}\n"
                f"An example configuration has been created. Please edit it with your device details."
            )

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f) or {}

        devices_list = config.get('devices', [])
        for device_data in devices_list:
            device = DeviceConfig(device_data)
            self.devices[device.name] = device

    def _create_example_config(self):
        """Create example devices.yaml file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        example = {
            'devices': [
                {
                    'name': 'router1',
                    'hostname': '192.168.1.1',
                    'username': 'admin',
                    'password': 'your-password-here',
                    'disabled': False,
                    'fallback_ip': None,
                    'private_key': None,
                }
            ]
        }

        with open(self.config_path, 'w') as f:
            f.write("# RouterOS MCP Server - Device Configuration\n")
            f.write("# Add your RouterOS devices below\n\n")
            yaml.dump(example, f, default_flow_style=False, sort_keys=False)

    def get_device(self, device_name: str) -> Optional[DeviceConfig]:
        """Get device by name."""
        return self.devices.get(device_name)

    def list_devices(self) -> List[DeviceConfig]:
        """List all non-disabled devices."""
        return [d for d in self.devices.values() if not d.disabled]

    def list_all_devices(self) -> List[DeviceConfig]:
        """List all devices including disabled ones."""
        return list(self.devices.values())


# Global settings instance
settings = Settings()
