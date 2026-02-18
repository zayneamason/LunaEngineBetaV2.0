"""
Animatronics Controller
=======================

Controls servo-based expressions:
- Head pan/tilt (look at targets)
- Ear positions (alert, relaxed, curious)
- Tail movement (happy wag, nervous twitch)
- Flipper gestures (wave, point, shrug)
"""

import asyncio
import logging
import random
from typing import Dict, Optional

from vehicle_os.core.types import Emotion
from vehicle_os.core.config import VehicleConfig

logger = logging.getLogger(__name__)


# Expression presets: servo positions for each emotion
# Values are -1.0 to 1.0 (center = 0)
EXPRESSION_PRESETS: Dict[Emotion, Dict[str, float]] = {
    Emotion.IDLE: {
        "head_pan": 0.0,
        "head_tilt": 0.0,
        "left_ear": 0.0,
        "right_ear": 0.0,
        "tail": 0.0,
        "left_flipper": -0.8,  # down
        "right_flipper": -0.8,
    },
    Emotion.LISTENING: {
        "head_pan": 0.0,
        "head_tilt": 0.1,  # slight upward tilt
        "left_ear": 0.5,   # ears forward
        "right_ear": 0.5,
        "tail": 0.0,
        "left_flipper": -0.8,
        "right_flipper": -0.8,
    },
    Emotion.THINKING: {
        "head_pan": 0.1,
        "head_tilt": 0.2,
        "left_ear": 0.2,
        "right_ear": -0.1,  # asymmetric = curiosity
        "tail": 0.1,
        "left_flipper": -0.6,
        "right_flipper": -0.8,
    },
    Emotion.SPEAKING: {
        "head_pan": 0.0,
        "head_tilt": 0.0,
        "left_ear": 0.3,
        "right_ear": 0.3,
        "tail": 0.2,
        "left_flipper": -0.5,
        "right_flipper": -0.5,
    },
    Emotion.HAPPY: {
        "head_pan": 0.0,
        "head_tilt": 0.1,
        "left_ear": 0.6,   # ears up
        "right_ear": 0.6,
        "tail": 0.0,       # will animate
        "left_flipper": 0.0,
        "right_flipper": 0.0,
    },
    Emotion.CURIOUS: {
        "head_pan": 0.2,
        "head_tilt": 0.3,
        "left_ear": 0.7,
        "right_ear": 0.4,
        "tail": 0.3,
        "left_flipper": -0.4,
        "right_flipper": -0.8,
    },
    Emotion.ALERT: {
        "head_pan": 0.0,
        "head_tilt": 0.2,
        "left_ear": 0.8,   # ears fully up
        "right_ear": 0.8,
        "tail": 0.0,
        "left_flipper": -0.3,
        "right_flipper": -0.3,
    },
    Emotion.TIRED: {
        "head_pan": 0.0,
        "head_tilt": -0.3,  # head down
        "left_ear": -0.4,   # ears drooped
        "right_ear": -0.4,
        "tail": -0.3,
        "left_flipper": -1.0,
        "right_flipper": -1.0,
    },
    Emotion.SLEEPING: {
        "head_pan": 0.0,
        "head_tilt": -0.5,
        "left_ear": -0.6,
        "right_ear": -0.6,
        "tail": -0.5,
        "left_flipper": -1.0,
        "right_flipper": -1.0,
    },
    Emotion.GREETING: {
        "head_pan": 0.0,
        "head_tilt": 0.1,
        "left_ear": 0.6,
        "right_ear": 0.6,
        "tail": 0.3,
        "left_flipper": 0.8,   # wave position
        "right_flipper": -0.5,
    },
}


class AnimatronicsController:
    """
    Controls all servo-based animatronics.
    
    Uses PCA9685 PWM driver board connected via I2C.
    """
    
    def __init__(self, config: VehicleConfig):
        self.config = config
        self._pca = None
        self._current_positions: Dict[str, float] = {}
        self._current_emotion = Emotion.IDLE
        self._animation_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def init(self):
        """Initialize PCA9685 servo driver"""
        try:
            # TODO: Initialize actual PCA9685
            # from adafruit_pca9685 import PCA9685
            # import board
            # i2c = board.I2C()
            # self._pca = PCA9685(i2c, address=self.config.animatronics.pca9685_address)
            # self._pca.frequency = 50  # 50Hz for servos
            
            # Set initial positions
            self._current_positions = EXPRESSION_PRESETS[Emotion.IDLE].copy()
            
            self._initialized = True
            logger.info("Animatronics controller initialized (stub mode)")
            
        except Exception as e:
            logger.error(f"Failed to initialize animatronics: {e}")
            raise
    
    async def express(self, emotion: Emotion):
        """
        Set expression to emotion preset.
        
        Smoothly transitions from current position to target.
        """
        self._current_emotion = emotion
        
        # Cancel any running animation
        if self._animation_task:
            self._animation_task.cancel()
        
        # Get target positions
        target = EXPRESSION_PRESETS.get(emotion, EXPRESSION_PRESETS[Emotion.IDLE])
        
        # Smooth transition
        await self._transition_to(target)
        
        # Start animation loop if needed
        if emotion == Emotion.HAPPY:
            self._animation_task = asyncio.create_task(self._tail_wag_animation())
        elif emotion == Emotion.GREETING:
            self._animation_task = asyncio.create_task(self._wave_animation())
        elif emotion == Emotion.SPEAKING:
            self._animation_task = asyncio.create_task(self._speaking_animation())
        
        logger.debug(f"Expression set to: {emotion.value}")
    
    async def look_at(self, x: float, y: float):
        """
        Point head toward target position.
        
        Args:
            x: -1.0 (left) to 1.0 (right)
            y: -1.0 (down) to 1.0 (up)
        """
        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))
        
        self._current_positions["head_pan"] = x
        self._current_positions["head_tilt"] = y
        
        await self._set_servo("head_pan", x)
        await self._set_servo("head_tilt", y)
    
    async def idle_animation(self):
        """Subtle idle animation - ear twitch, slight movements"""
        if self._current_emotion not in (Emotion.IDLE, Emotion.SLEEPING):
            return
        
        # Random ear twitch
        if random.random() < 0.3:
            ear = random.choice(["left_ear", "right_ear"])
            twitch = random.uniform(-0.1, 0.2)
            current = self._current_positions.get(ear, 0)
            
            await self._set_servo(ear, current + twitch)
            await asyncio.sleep(0.15)
            await self._set_servo(ear, current)
        
        # Occasional tail swish
        if random.random() < 0.1:
            current_tail = self._current_positions.get("tail", 0)
            await self._set_servo("tail", current_tail + 0.2)
            await asyncio.sleep(0.2)
            await self._set_servo("tail", current_tail - 0.1)
            await asyncio.sleep(0.15)
            await self._set_servo("tail", current_tail)
    
    async def _transition_to(self, target: Dict[str, float], duration: float = None):
        """Smoothly transition to target positions"""
        duration = duration or self.config.animatronics.expression_transition_time
        steps = int(duration / 0.02)  # 50Hz update rate
        
        if steps < 1:
            steps = 1
        
        start_positions = self._current_positions.copy()
        
        for step in range(steps + 1):
            t = step / steps  # 0.0 to 1.0
            # Ease in-out
            t = t * t * (3 - 2 * t)
            
            for servo, target_pos in target.items():
                start_pos = start_positions.get(servo, 0)
                current_pos = start_pos + (target_pos - start_pos) * t
                await self._set_servo(servo, current_pos)
            
            await asyncio.sleep(0.02)
        
        self._current_positions = target.copy()
    
    async def _set_servo(self, name: str, position: float):
        """
        Set servo position.
        
        Args:
            name: Servo name (head_pan, head_tilt, etc.)
            position: -1.0 to 1.0
        """
        position = max(-1.0, min(1.0, position))
        self._current_positions[name] = position
        
        # Map servo name to channel
        channel_map = {
            "head_pan": self.config.animatronics.head_pan_channel,
            "head_tilt": self.config.animatronics.head_tilt_channel,
            "tail": self.config.animatronics.tail_channel,
            "left_ear": self.config.animatronics.left_ear_channel,
            "right_ear": self.config.animatronics.right_ear_channel,
            "left_flipper": self.config.animatronics.left_flipper_channel,
            "right_flipper": self.config.animatronics.right_flipper_channel,
        }
        
        channel = channel_map.get(name)
        if channel is None:
            return
        
        # Convert position to pulse width
        center = self.config.animatronics.servo_center
        range_us = (self.config.animatronics.servo_max - self.config.animatronics.servo_min) / 2
        pulse_us = center + (position * range_us)
        
        # TODO: Actually set servo via PCA9685
        # if self._pca:
        #     self._pca.channels[channel].duty_cycle = int(pulse_us / 20000 * 65535)
        
        logger.debug(f"Servo {name} (ch{channel}): {position:.2f} -> {pulse_us:.0f}us")
    
    # ==================== Animation Loops ====================
    
    async def _tail_wag_animation(self):
        """Happy tail wag animation"""
        try:
            while True:
                await self._set_servo("tail", 0.5)
                await asyncio.sleep(0.25)
                await self._set_servo("tail", -0.5)
                await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            await self._set_servo("tail", 0)
    
    async def _wave_animation(self):
        """Greeting wave animation"""
        try:
            for _ in range(3):  # Wave 3 times
                await self._set_servo("left_flipper", 1.0)
                await asyncio.sleep(0.2)
                await self._set_servo("left_flipper", 0.5)
                await asyncio.sleep(0.2)
            # Return to greeting pose
            await self._set_servo("left_flipper", 0.8)
        except asyncio.CancelledError:
            pass
    
    async def _speaking_animation(self):
        """Subtle movement while speaking"""
        try:
            while True:
                # Slight head movements
                await self._set_servo("head_tilt", random.uniform(-0.1, 0.15))
                await self._set_servo("head_pan", random.uniform(-0.1, 0.1))
                await asyncio.sleep(random.uniform(0.3, 0.6))
        except asyncio.CancelledError:
            pass
