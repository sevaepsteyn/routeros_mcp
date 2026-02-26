"""Main entry point for RouterOS MCP server."""

import logging
import os
import sys

from routeros_mcp.server import mcp
from routeros_mcp.settings import settings


def setup_logging():
    """Configure logging based on settings."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from libraries
    logging.getLogger("routeros_api").setLevel(logging.WARNING)
    logging.getLogger("paramiko").setLevel(logging.WARNING)


def main():
    """Run the RouterOS MCP server."""
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting RouterOS MCP Server")
    logger.info(f"API Port: {settings.routeros_api_port}")
    logger.info(f"API SSL Port: {settings.routeros_api_ssl_port}")
    logger.info(f"SSH Port: {settings.routeros_ssh_port}")
    logger.info(f"Connection Order: {', '.join(settings.routeros_connection_order)}")
    logger.info(f"Timeout: {settings.routeros_timeout}s")

    try:
        # This will load devices and create example config if needed
        from routeros_mcp.settings import DeviceManager
        config_path = settings.get_devices_config_path()
        device_manager = DeviceManager(config_path)
        logger.info(f"Loaded {len(device_manager.list_devices())} active device(s)")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading device configuration: {e}", exc_info=True)
        sys.exit(1)

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    port = int(os.environ.get("MCP_PORT", "8000"))

    try:
        if transport == "streamable-http":
            logger.info(f"Running with streamable-http transport on port {port}")
            mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
        else:
            mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
