#!/usr/bin/env python3
"""
Luna Driver Example
===================

Example showing how Luna Engine connects to Vehicle OS as a driver.

Luna is the personality/AI - Vehicle OS is the body.
This file shows the integration point.
"""

import asyncio
import logging

from vehicle_os import DriverClient

logger = logging.getLogger(__name__)


class LunaDriver:
    """
    Luna's interface to the robot body.
    
    This class bridges Luna Engine (AI, memory, conversation) with
    Vehicle OS (motors, sensors, expression).
    
    Luna calls high-level methods like:
        - respond_to_person(face_id, response_text)
        - express_emotion(emotion)
        - approach_person(face_id)
        - idle()
    
    This driver translates those into Vehicle OS commands.
    """
    
    def __init__(self):
        self.client = DriverClient()
        self.connected = False
        self._known_faces = {}  # face_id -> name mapping
    
    async def connect(self):
        """Connect to Vehicle OS"""
        if await self.client.connect():
            await self.client.identify("Luna")
            self.connected = True
            logger.info("Luna connected to body")
            return True
        return False
    
    async def disconnect(self):
        """Disconnect from Vehicle OS"""
        await self.client.disconnect()
        self.connected = False
    
    # ==================== High-Level Actions ====================
    
    async def respond_to_person(self, text: str, look_at_face: bool = True):
        """
        Respond to a person with speech and expression.
        
        Args:
            text: What to say
            look_at_face: Whether to look at the detected face
        """
        if not self.connected:
            return
        
        # Look at person if requested
        if look_at_face:
            faces = await self.client.get_faces()
            if faces:
                # Look at first/nearest face
                face = faces[0]
                bbox = face.get("bbox", [0, 0, 0, 0])
                # Convert bbox center to -1 to 1 range
                # Assuming 640x480 frame
                x = (bbox[0] + bbox[2] / 2) / 640 * 2 - 1
                y = -((bbox[1] + bbox[3] / 2) / 480 * 2 - 1)  # Flip Y
                await self.client.look_at(x, y)
        
        # Express speaking emotion and say the text
        await self.client.say(text)
    
    async def greet(self, name: str = None):
        """
        Perform greeting behavior.
        
        Args:
            name: Person's name if known
        """
        await self.client.express("greeting")
        
        if name:
            await self.client.say(f"Hello {name}! Good to see you again.")
        else:
            await self.client.say("Hello! Nice to meet you.")
        
        await asyncio.sleep(1)
        await self.client.express("happy")
    
    async def listen(self):
        """Enter listening posture"""
        await self.client.express("listening")
    
    async def think(self):
        """Enter thinking posture (while processing)"""
        await self.client.express("thinking")
    
    async def idle(self):
        """Return to idle state"""
        await self.client.express("idle")
    
    async def approach_person(self, target_distance: float = 1.5):
        """
        Approach the nearest detected person.
        
        Args:
            target_distance: How close to get (meters)
        """
        # TODO: Implement using person follower or navigation
        pass
    
    async def wander(self, duration: float = 30.0):
        """
        Wander around looking for people.
        
        Args:
            duration: How long to wander (seconds)
        """
        import random
        
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < duration:
            # Check for faces
            faces = await self.client.get_faces()
            if faces:
                # Found someone - stop wandering
                return True
            
            # Random movement
            direction = random.choice(["forward", "left", "right"])
            await self.client.move(direction, 0.3)
            await asyncio.sleep(random.uniform(1, 3))
            await self.client.stop()
            
            # Look around
            await self.client.look_at(random.uniform(-0.5, 0.5), random.uniform(-0.2, 0.2))
            await asyncio.sleep(0.5)
        
        return False  # Didn't find anyone
    
    async def return_home(self):
        """Return to charging hub"""
        await self.client.express("tired")
        await self.client.say("I'm heading back to rest.")
        await self.client.go_home()
    
    # ==================== Sensor Access ====================
    
    async def see_faces(self):
        """Get currently visible faces"""
        return await self.client.get_faces()
    
    async def get_status(self):
        """Get body status"""
        return await self.client.get_status()
    
    async def is_low_battery(self, threshold: int = 20):
        """Check if battery is low"""
        status = await self.client.get_status()
        return status.get("battery_percent", 100) < threshold


# ==================== Example Usage ====================

async def example_conversation():
    """Example of Luna using the driver"""
    
    luna = LunaDriver()
    
    if not await luna.connect():
        print("Failed to connect to body")
        return
    
    try:
        # Check battery
        if await luna.is_low_battery():
            await luna.return_home()
            return
        
        # Greet
        await luna.greet()
        
        # Have a conversation (this would come from Luna Engine)
        await luna.listen()
        await asyncio.sleep(2)  # Simulating hearing input
        
        await luna.think()
        await asyncio.sleep(1)  # Simulating processing
        
        await luna.respond_to_person(
            "That's a great question! The Salton Sea was actually created by accident "
            "in 1905 when irrigation canals from the Colorado River broke through."
        )
        
        await asyncio.sleep(2)
        await luna.idle()
        
    finally:
        await luna.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_conversation())
