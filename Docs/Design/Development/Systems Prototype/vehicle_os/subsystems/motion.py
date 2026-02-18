"""
Motion Controller
=================

Handles drivetrain control for 4WD skid-steer platform.
Communicates with Teensy over serial for real-time motor control.
"""

import asyncio
import logging
from typing import Optional

from vehicle_os.core.types import Direction
from vehicle_os.core.config import VehicleConfig

logger = logging.getLogger(__name__)


class MotionController:
    """
    Controls the 4WD skid-steer drivetrain.
    
    Motor layout (top view):
        [FL]----[FR]
          |      |
          |      |
        [BL]----[BR]
    
    Skid steer turns by running left and right sides at different speeds.
    """
    
    def __init__(self, config: VehicleConfig):
        self.config = config
        self._serial = None
        self._current_direction = Direction.STOP
        self._current_speed = 0.0
        self._initialized = False
    
    async def init(self):
        """Initialize serial connection to Teensy"""
        try:
            # TODO: Implement actual serial connection
            # import serial_asyncio
            # self._serial = await serial_asyncio.open_serial_connection(
            #     url=self.config.hardware.teensy_port,
            #     baudrate=self.config.hardware.teensy_baud
            # )
            
            self._initialized = True
            logger.info("Motion controller initialized (stub mode)")
            
        except Exception as e:
            logger.error(f"Failed to initialize motion controller: {e}")
            raise
    
    async def move(self, direction: Direction, speed: float = 0.5):
        """
        Move in specified direction.
        
        Args:
            direction: Direction enum
            speed: 0.0 to 1.0 (percentage of max speed)
        """
        # Clamp speed
        speed = max(0.0, min(1.0, speed)) * self.config.motion.max_speed
        
        self._current_direction = direction
        self._current_speed = speed
        
        # Calculate motor speeds for skid steer
        left_speed, right_speed = self._calculate_motor_speeds(direction, speed)
        
        # Send to Teensy
        await self._send_motor_command(left_speed, right_speed)
        
        logger.debug(f"Move: {direction.value} at {speed:.2f} (L:{left_speed:.2f}, R:{right_speed:.2f})")
    
    async def stop(self):
        """Stop all motors immediately"""
        self._current_direction = Direction.STOP
        self._current_speed = 0.0
        
        await self._send_motor_command(0, 0)
        logger.debug("Motors stopped")
    
    async def set_motor_speeds(self, left: float, right: float):
        """
        Direct motor control (for advanced navigation).
        
        Args:
            left: -1.0 to 1.0 (negative = reverse)
            right: -1.0 to 1.0
        """
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        
        await self._send_motor_command(left, right)
    
    def _calculate_motor_speeds(self, direction: Direction, speed: float) -> tuple[float, float]:
        """
        Calculate left/right motor speeds for skid steer.
        
        Returns:
            (left_speed, right_speed) each -1.0 to 1.0
        """
        turn_rate = self.config.motion.turn_rate
        
        if direction == Direction.STOP:
            return 0, 0
        
        elif direction == Direction.FORWARD:
            return speed, speed
        
        elif direction == Direction.BACKWARD:
            return -speed, -speed
        
        elif direction == Direction.LEFT:
            # Turn left: right side faster
            return speed * (1 - turn_rate), speed
        
        elif direction == Direction.RIGHT:
            # Turn right: left side faster
            return speed, speed * (1 - turn_rate)
        
        elif direction == Direction.SPIN_LEFT:
            # Spin in place: opposite directions
            return -speed, speed
        
        elif direction == Direction.SPIN_RIGHT:
            return speed, -speed
        
        return 0, 0
    
    async def _send_motor_command(self, left: float, right: float):
        """Send motor speeds to Teensy"""
        if not self._initialized:
            return
        
        # Protocol: "M <left_pwm> <right_pwm>\n"
        # PWM values: -255 to 255
        left_pwm = int(left * 255)
        right_pwm = int(right * 255)
        
        command = f"M {left_pwm} {right_pwm}\n"
        
        if self._serial:
            # TODO: Actually send over serial
            # self._serial.write(command.encode())
            pass
        
        logger.debug(f"Motor command: {command.strip()}")
    
    async def get_encoder_counts(self) -> tuple[int, int, int, int]:
        """
        Get wheel encoder counts.
        
        Returns:
            (front_left, front_right, back_left, back_right)
        """
        # TODO: Request from Teensy
        return 0, 0, 0, 0
    
    async def reset_encoders(self):
        """Reset encoder counts to zero"""
        if self._serial:
            # TODO: Send reset command
            pass
    
    @property
    def is_moving(self) -> bool:
        return self._current_speed > 0 and self._current_direction != Direction.STOP
