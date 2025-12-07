"""Custom exceptions for RouterOS MCP server."""


class RouterOSMCPError(Exception):
    """Base exception for RouterOS MCP errors."""
    pass


class DeviceNotFoundError(RouterOSMCPError):
    """Device not found in configuration."""
    pass


class DeviceDisabledError(RouterOSMCPError):
    """Device is disabled in configuration."""
    pass


class ConnectionError(RouterOSMCPError):
    """Failed to connect to RouterOS device."""
    pass


class AuthenticationError(RouterOSMCPError):
    """Authentication failed."""
    pass


class APIError(RouterOSMCPError):
    """RouterOS API error."""
    pass


class SSHError(RouterOSMCPError):
    """SSH connection error."""
    pass


class ConfigurationError(RouterOSMCPError):
    """Configuration file error."""
    pass
