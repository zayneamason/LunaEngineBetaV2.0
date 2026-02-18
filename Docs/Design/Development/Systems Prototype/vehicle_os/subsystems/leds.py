"""
LED Controller
==============

Controls all LED lighting:
- Eye displays (OLED or LED matrix)
- Chest glow
- Fiber optic tail
- Underglow
"""

import asyncio
import logging
from typing import Tuple, Optional

from vehicle_os.core.types import Emotion
from vehicle_os.core.config import VehicleConfig

logger = logging.getLogger(__name__)


# Color presets for each emotion (RGB)
EMOTION_COLORS = {
    Emotion.IDLE: (0, 100, 150),       # Soft cyan
    Emotion.LISTENING: (0, 150, 200),   # Brighter cyan
    Emotion.THINKING: (100, 50, 200),   # Purple
    Emotion.SPEAKING: (0, 200, 150),    # Teal
    Emotion.HAPPY: (200, 150, 0),       # Warm gold
    Emotion.CURIOUS: (150, 100, 200),   # Light purple
    Emotion.ALERT: (200, 100, 0),       # Orange
    Emotion.TIRED: (50, 50, 100),       # Dim blue
    Emotion.SLEEPING: (20, 20, 50),     # Very dim
    Emotion.GREETING: (100, 200, 150),  # Friendly green-cyan
}


class LEDController:
    """
    Controls WS2812B LED strips and OLED eye displays.
    """
    
    def __init__(self, config: VehicleConfig):
        self.config = config
        self._strip = None
        self._current_color = (0, 0, 0)
        self._current_brightness = config.led.brightness
        self._animation_task: Optional[asyncio.Task] = None
        self._initialized = False
    
    async def init(self):
        """Initialize LED hardware"""
        try:
            # TODO: Initialize actual NeoPixel strip
            # import neopixel
            # import board
            # 
            # total_leds = (
            #     self.config.led.eye_left_count +
            #     self.config.led.eye_right_count +
            #     self.config.led.chest_count +
            #     self.config.led.tail_count +
            #     self.config.led.underglow_count
            # )
            # self._strip = neopixel.NeoPixel(board.D18, total_leds, brightness=0.5)
            
            self._initialized = True
            logger.info("LED controller initialized (stub mode)")
            
        except Exception as e:
            logger.error(f"Failed to initialize LEDs: {e}")
            raise
    
    async def express(self, emotion: Emotion):
        """
        Set LED expression for emotion.
        """
        # Cancel any running animation
        if self._animation_task:
            self._animation_task.cancel()
        
        color = EMOTION_COLORS.get(emotion, (0, 100, 150))
        self._current_color = color
        
        # Set base color
        await self._set_all_color(color)
        
        # Start animation if needed
        if emotion == Emotion.IDLE:
            self._animation_task = asyncio.create_task(self._idle_pulse())
        elif emotion == Emotion.THINKING:
            self._animation_task = asyncio.create_task(self._thinking_swirl())
        elif emotion == Emotion.SPEAKING:
            self._animation_task = asyncio.create_task(self._speaking_pulse())
        elif emotion == Emotion.HAPPY:
            self._animation_task = asyncio.create_task(self._happy_sparkle())
        elif emotion == Emotion.SLEEPING:
            self._animation_task = asyncio.create_task(self._sleep_breathe())
        
        logger.debug(f"LED expression: {emotion.value} -> RGB{color}")
    
    async def set_color(self, zone: str, color: Tuple[int, int, int]):
        """
        Set color for specific zone.
        
        Args:
            zone: eyes, chest, tail, underglow, all
            color: RGB tuple (0-255 each)
        """
        r, g, b = color
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        # TODO: Map zones to LED ranges and set colors
        logger.debug(f"Set {zone} color to RGB({r}, {g}, {b})")
    
    async def set_brightness(self, brightness: int):
        """
        Set global brightness.
        
        Args:
            brightness: 0-255
        """
        self._current_brightness = max(0, min(255, brightness))
        
        # TODO: Apply to strip
        logger.debug(f"Brightness set to {self._current_brightness}")
    
    async def _set_all_color(self, color: Tuple[int, int, int]):
        """Set all LEDs to color"""
        # TODO: Actually set strip colors
        pass
    
    # ==================== Animations ====================
    
    async def _idle_pulse(self):
        """Slow breathing pulse for idle state"""
        try:
            while True:
                # Breathe in
                for i in range(50, 128, 2):
                    await self.set_brightness(i)
                    await asyncio.sleep(0.03)
                # Breathe out
                for i in range(128, 50, -2):
                    await self.set_brightness(i)
                    await asyncio.sleep(0.03)
        except asyncio.CancelledError:
            await self.set_brightness(self.config.led.brightness)
    
    async def _thinking_swirl(self):
        """Purple swirl for thinking"""
        try:
            position = 0
            while True:
                # TODO: Animate a swirl pattern
                position = (position + 1) % 100
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
    
    async def _speaking_pulse(self):
        """Pulse with speech rhythm"""
        try:
            while True:
                # Quick pulse
                await self.set_brightness(200)
                await asyncio.sleep(0.1)
                await self.set_brightness(100)
                await asyncio.sleep(0.15)
        except asyncio.CancelledError:
            await self.set_brightness(self.config.led.brightness)
    
    async def _happy_sparkle(self):
        """Sparkle effect for happy"""
        try:
            import random
            while True:
                # Random bright spots
                # TODO: Set random LEDs to bright white briefly
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
    
    async def _sleep_breathe(self):
        """Very slow dim breathing for sleep"""
        try:
            while True:
                for i in range(10, 40, 1):
                    await self.set_brightness(i)
                    await asyncio.sleep(0.1)
                for i in range(40, 10, -1):
                    await self.set_brightness(i)
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass


class OLEDEyes:
    """
    Controls OLED eye displays for expressive eyes.
    """
    
    def __init__(self, config: VehicleConfig):
        self.config = config
        self._left_display = None
        self._right_display = None
    
    async def init(self):
        """Initialize OLED displays"""
        # TODO: Initialize SSD1306 or similar
        pass
    
    async def set_expression(self, expression: str):
        """
        Set eye expression.
        
        Args:
            expression: normal, happy, sad, angry, surprised, sleepy, wink
        """
        # TODO: Draw appropriate eye shapes
        pass
    
    async def look_at(self, x: float, y: float):
        """
        Move eye pupils to look at position.
        
        Args:
            x: -1.0 (left) to 1.0 (right)
            y: -1.0 (down) to 1.0 (up)
        """
        # TODO: Offset pupil position on displays
        pass
    
    async def blink(self):
        """Trigger a blink animation"""
        # TODO: Quick close-open animation
        pass
