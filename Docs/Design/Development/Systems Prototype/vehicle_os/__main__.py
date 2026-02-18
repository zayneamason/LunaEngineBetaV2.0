#!/usr/bin/env python3
"""
Vehicle OS - Main Entry Point
=============================

Start the Vehicle OS server:
    python -m vehicle_os

Or with options:
    python -m vehicle_os --debug --config /path/to/config.json
"""

import argparse
import asyncio
import signal
import sys

from vehicle_os.core.server import VehicleServer
from vehicle_os.core.config import VehicleConfig, set_config
from vehicle_os.utils.logging import setup_logging


def parse_args():
    parser = argparse.ArgumentParser(
        description="Vehicle OS - Modular Robot Operating System"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--socket", "-s",
        help="Unix socket path (default: /tmp/vehicle_os.sock)"
    )
    parser.add_argument(
        "--log-file", "-l",
        help="Log file path"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level, log_file=args.log_file)
    
    # Load config
    if args.config:
        config = VehicleConfig.load(args.config)
    else:
        config = VehicleConfig()
    
    if args.socket:
        config.server.socket_path = args.socket
    
    config.debug = args.debug
    set_config(config)
    
    # Create server
    server = VehicleServer(config)
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def shutdown_handler():
        asyncio.create_task(server.stop())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown_handler)
    
    # Start server
    print("""
    ╔═══════════════════════════════════════════╗
    ║          VEHICLE OS v0.1.0                ║
    ║   Modular Robot Operating System          ║
    ╚═══════════════════════════════════════════╝
    """)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
