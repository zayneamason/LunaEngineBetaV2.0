"""
Vehicle OS Subsystems
=====================

Hardware abstraction modules for each subsystem:
- Motion: Drivetrain control
- Animatronics: Servo-based expression
- LEDs: Lighting and visual feedback
- Audio: TTS and music playback
- Sensors: Camera, IMU, GPS, etc.
- Navigation: Pathfinding and autonomous movement
"""

from vehicle_os.subsystems.motion import MotionController
from vehicle_os.subsystems.animatronics import AnimatronicsController
from vehicle_os.subsystems.leds import LEDController
from vehicle_os.subsystems.audio import AudioController
from vehicle_os.subsystems.sensors import SensorController
from vehicle_os.subsystems.navigation import NavigationController

__all__ = [
    "MotionController",
    "AnimatronicsController",
    "LEDController",
    "AudioController",
    "SensorController",
    "NavigationController",
]
