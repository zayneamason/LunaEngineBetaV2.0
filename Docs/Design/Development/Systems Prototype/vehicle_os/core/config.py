"""
Vehicle OS Configuration
========================

Central configuration for all subsystems.
Can be loaded from YAML file or set programmatically.
"""

from dataclasses import dataclass, field
from typing import Optional
import os
import json


@dataclass
class MotionConfig:
    """Motion/drivetrain settings"""
    max_speed: float = 0.5  # 0-1, percentage of max
    acceleration: float = 0.3  # 0-1, ramp rate
    turn_rate: float = 0.5  # 0-1
    wheel_base: float = 0.4  # meters between wheels
    wheel_diameter: float = 0.2  # meters (8 inches)
    encoder_ticks_per_rev: int = 360


@dataclass
class SafetyConfig:
    """Safety system thresholds"""
    # Collision avoidance
    min_obstacle_distance: float = 0.6  # meters (2 feet)
    slow_zone_distance: float = 1.5  # meters
    
    # Thermal limits (Celsius)
    cpu_temp_warning: float = 75.0
    cpu_temp_critical: float = 85.0
    enclosure_temp_warning: float = 50.0
    enclosure_temp_critical: float = 60.0
    
    # Battery
    battery_low_percent: int = 20
    battery_critical_percent: int = 10
    
    # Tilt (degrees)
    max_tilt_angle: float = 30.0
    
    # Watchdog
    driver_timeout_seconds: float = 30.0  # idle if no commands
    heartbeat_interval: float = 5.0


@dataclass
class NavigationConfig:
    """Navigation settings"""
    # Home position (GPS)
    home_lat: float = 33.3528  # Bombay Beach approximate
    home_lon: float = -115.7292
    home_radius: float = 2.0  # meters - "close enough"
    
    # Pathfinding
    waypoint_radius: float = 1.0  # meters - reached waypoint
    gps_update_rate: float = 1.0  # Hz


@dataclass
class AnimatronicsConfig:
    """Servo and expression settings"""
    # Servo channels on PCA9685
    head_pan_channel: int = 0
    head_tilt_channel: int = 1
    tail_channel: int = 2
    left_ear_channel: int = 3
    right_ear_channel: int = 4
    left_flipper_channel: int = 5
    right_flipper_channel: int = 6
    
    # Servo limits (pulse width in microseconds)
    servo_min: int = 500
    servo_max: int = 2500
    servo_center: int = 1500
    
    # Movement speed
    expression_transition_time: float = 0.3  # seconds


@dataclass
class LEDConfig:
    """LED and lighting settings"""
    # WS2812B strip lengths
    eye_left_count: int = 16
    eye_right_count: int = 16
    chest_count: int = 24
    tail_count: int = 30
    underglow_count: int = 20
    
    # Default brightness (0-255)
    brightness: int = 128
    
    # Colors (RGB)
    color_idle: tuple = (0, 100, 150)  # cyan
    color_listening: tuple = (0, 150, 200)
    color_thinking: tuple = (100, 50, 200)  # purple
    color_speaking: tuple = (0, 200, 150)
    color_happy: tuple = (200, 150, 0)  # warm
    color_alert: tuple = (200, 100, 0)  # orange
    color_low_battery: tuple = (200, 100, 0)  # amber


@dataclass
class AudioConfig:
    """Audio system settings"""
    # Volume (0-100)
    voice_volume: int = 80
    music_volume: int = 60
    
    # TTS
    tts_voice: str = "default"
    tts_rate: int = 150  # words per minute


@dataclass
class HardwareConfig:
    """Hardware interface settings"""
    # Serial connection to Teensy
    teensy_port: str = "/dev/ttyACM0"
    teensy_baud: int = 115200
    
    # I2C addresses
    pca9685_address: int = 0x40
    bno055_address: int = 0x28
    
    # GPIO pins (if using Jetson GPIO)
    emergency_stop_pin: int = 17
    status_led_pin: int = 18


@dataclass
class ServerConfig:
    """Unix socket server settings"""
    socket_path: str = "/tmp/vehicle_os.sock"
    max_connections: int = 1  # only one driver at a time
    buffer_size: int = 65536


@dataclass
class VehicleConfig:
    """Master configuration"""
    motion: MotionConfig = field(default_factory=MotionConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    navigation: NavigationConfig = field(default_factory=NavigationConfig)
    animatronics: AnimatronicsConfig = field(default_factory=AnimatronicsConfig)
    led: LEDConfig = field(default_factory=LEDConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    
    # Debug
    debug: bool = False
    log_level: str = "INFO"
    
    @classmethod
    def load(cls, path: str) -> "VehicleConfig":
        """Load configuration from JSON file"""
        if not os.path.exists(path):
            return cls()
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        config = cls()
        # TODO: Deep merge from data
        return config
    
    def save(self, path: str):
        """Save configuration to JSON file"""
        # TODO: Serialize dataclasses to dict
        pass


# Default configuration singleton
_default_config: Optional[VehicleConfig] = None

def get_config() -> VehicleConfig:
    """Get the global configuration"""
    global _default_config
    if _default_config is None:
        _default_config = VehicleConfig()
    return _default_config

def set_config(config: VehicleConfig):
    """Set the global configuration"""
    global _default_config
    _default_config = config
