"""
Vehicle OS Core Types
====================

Shared types, enums, and data classes used throughout the system.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import time


class Emotion(Enum):
    """Animatronic + LED expression states"""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    HAPPY = "happy"
    CURIOUS = "curious"
    ALERT = "alert"
    TIRED = "tired"
    SLEEPING = "sleeping"
    GREETING = "greeting"
    

class Direction(Enum):
    """Movement directions"""
    FORWARD = "forward"
    BACKWARD = "backward"
    LEFT = "left"
    RIGHT = "right"
    STOP = "stop"
    SPIN_LEFT = "spin_left"
    SPIN_RIGHT = "spin_right"


class ThermalStatus(Enum):
    """Thermal conditions"""
    NORMAL = "normal"      # < 85°F - full operation
    WARM = "warm"          # 85-95°F - active cooling
    HOT = "hot"            # 95-105°F - reduced duty
    CRITICAL = "critical"  # > 105°F - return to hub


class SafetyState(Enum):
    """Safety system states"""
    OK = "ok"
    OBSTACLE_DETECTED = "obstacle_detected"
    CLIFF_DETECTED = "cliff_detected"
    TILT_WARNING = "tilt_warning"
    COLLISION = "collision"
    THERMAL_LIMIT = "thermal_limit"
    LOW_BATTERY = "low_battery"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class Position:
    """GPS position"""
    lat: float = 0.0
    lon: float = 0.0
    heading: float = 0.0  # degrees, 0 = north
    accuracy: float = 0.0  # meters
    timestamp: float = field(default_factory=time.time)


@dataclass
class Face:
    """Detected face with embedding"""
    id: str  # temporary ID for this session
    embedding: List[float]  # 128-dim face embedding
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class Status:
    """Complete vehicle status"""
    # Power
    battery_percent: int = 100
    battery_voltage: float = 25.2
    charging: bool = False
    
    # Thermal
    thermal: ThermalStatus = ThermalStatus.NORMAL
    cpu_temp: float = 45.0
    enclosure_temp: float = 30.0
    battery_temp: float = 25.0
    
    # Position
    position: Position = field(default_factory=Position)
    
    # Safety
    safety: SafetyState = SafetyState.OK
    
    # Driver
    driver_connected: bool = False
    driver_name: str = ""
    
    # System
    uptime: float = 0.0
    current_emotion: Emotion = Emotion.IDLE
    
    def to_dict(self) -> dict:
        """Serialize for JSON transport"""
        return {
            "battery_percent": self.battery_percent,
            "battery_voltage": self.battery_voltage,
            "charging": self.charging,
            "thermal": self.thermal.value,
            "cpu_temp": self.cpu_temp,
            "enclosure_temp": self.enclosure_temp,
            "battery_temp": self.battery_temp,
            "position": {
                "lat": self.position.lat,
                "lon": self.position.lon,
                "heading": self.position.heading,
                "accuracy": self.position.accuracy,
            },
            "safety": self.safety.value,
            "driver_connected": self.driver_connected,
            "driver_name": self.driver_name,
            "uptime": self.uptime,
            "current_emotion": self.current_emotion.value,
        }


@dataclass 
class Command:
    """Command from driver to Vehicle OS"""
    action: str
    params: dict = field(default_factory=dict)
    id: str = ""  # for request/response matching
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "params": self.params,
            "id": self.id,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Command":
        return cls(
            action=data.get("action", ""),
            params=data.get("params", {}),
            id=data.get("id", ""),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class Response:
    """Response from Vehicle OS to driver"""
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    id: str = ""  # matches Command.id
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "id": self.id,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Response":
        return cls(
            success=data.get("success", False),
            data=data.get("data", {}),
            error=data.get("error", ""),
            id=data.get("id", ""),
            timestamp=data.get("timestamp", time.time()),
        )
