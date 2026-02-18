"""
Vehicle OS - Modular Robot Operating System
==========================================

A swappable driver architecture for autonomous robots.
Luna is the driver, Vehicle OS is the vehicle.

The driver (Luna, remote operator, or any agent) connects via Unix socket
and sends commands. Vehicle OS handles all hardware abstraction, safety,
and low-level control.

Architecture:
    Driver (Luna) <--Unix Socket--> Vehicle OS <--Serial--> Teensy <--> Hardware

Usage:
    # Start the Vehicle OS server
    from vehicle_os import VehicleServer
    server = VehicleServer()
    await server.start()
    
    # Connect a driver
    from vehicle_os import DriverClient
    client = DriverClient()
    await client.connect()
    await client.move("forward", 0.5)
    await client.express("happy")
"""

__version__ = "0.1.0"
__author__ = "Ahab / Project Tapestry"

from vehicle_os.core.server import VehicleServer
from vehicle_os.core.client import DriverClient
from vehicle_os.core.types import Emotion, Direction, Status
from vehicle_os.core.config import VehicleConfig

__all__ = [
    "VehicleServer",
    "DriverClient", 
    "Emotion",
    "Direction",
    "Status",
    "VehicleConfig",
]
