"""
Vehicle OS Driver Client
========================

Client library for drivers (Luna, remote operators, scripts) to connect
to Vehicle OS and send commands.
"""

import asyncio
import json
import logging
import uuid
from typing import Optional, Dict, Any, List

from vehicle_os.core.types import Command, Response, Status, Emotion, Direction, Face
from vehicle_os.core.config import VehicleConfig, get_config

logger = logging.getLogger(__name__)


class DriverClient:
    """
    Client for connecting to Vehicle OS as a driver.
    
    Usage:
        client = DriverClient()
        await client.connect()
        await client.identify("Luna")
        
        await client.move("forward", 0.5)
        await client.express("happy")
        await client.say("Hello!")
        
        status = await client.get_status()
        print(f"Battery: {status['battery_percent']}%")
        
        await client.disconnect()
    """
    
    def __init__(self, config: Optional[VehicleConfig] = None):
        self.config = config or get_config()
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._response_task: Optional[asyncio.Task] = None
    
    async def connect(self, socket_path: Optional[str] = None) -> bool:
        """Connect to Vehicle OS server"""
        path = socket_path or self.config.server.socket_path
        
        try:
            self.reader, self.writer = await asyncio.open_unix_connection(path)
            self.connected = True
            
            # Start response listener
            self._response_task = asyncio.create_task(self._response_listener())
            
            logger.info(f"Connected to Vehicle OS at {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Vehicle OS"""
        if self._response_task:
            self._response_task.cancel()
        
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        
        self.connected = False
        logger.info("Disconnected from Vehicle OS")
    
    async def _response_listener(self):
        """Listen for responses from server"""
        try:
            while self.connected and self.reader:
                data = await self.reader.readline()
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode())
                    response = Response.from_dict(msg)
                    
                    # Match to pending request
                    if response.id in self._pending_responses:
                        self._pending_responses[response.id].set_result(response)
                        del self._pending_responses[response.id]
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid response: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Response listener error: {e}")
            self.connected = False
    
    async def _send_command(self, action: str, params: Dict[str, Any] = None) -> Response:
        """Send command and wait for response"""
        if not self.connected or not self.writer:
            raise ConnectionError("Not connected to Vehicle OS")
        
        cmd_id = str(uuid.uuid4())[:8]
        command = Command(action=action, params=params or {}, id=cmd_id)
        
        # Create future for response
        future = asyncio.Future()
        self._pending_responses[cmd_id] = future
        
        # Send command
        self.writer.write(json.dumps(command.to_dict()).encode() + b'\n')
        await self.writer.drain()
        
        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            del self._pending_responses[cmd_id]
            raise TimeoutError(f"Command {action} timed out")
    
    # ==================== Movement ====================
    
    async def move(self, direction: str, speed: float = 0.5) -> bool:
        """
        Move in a direction.
        
        Args:
            direction: forward, backward, left, right, spin_left, spin_right
            speed: 0.0 to 1.0
        
        Returns:
            True if command succeeded
        """
        response = await self._send_command("move", {
            "direction": direction,
            "speed": max(0.0, min(1.0, speed))
        })
        return response.success
    
    async def stop(self) -> bool:
        """Stop all movement"""
        response = await self._send_command("stop")
        return response.success
    
    async def go_to(self, lat: float, lon: float) -> bool:
        """
        Navigate to GPS coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
        
        Returns:
            True if navigation started
        """
        response = await self._send_command("go_to", {"lat": lat, "lon": lon})
        return response.success
    
    async def go_home(self) -> bool:
        """Navigate back to hub"""
        response = await self._send_command("go_home")
        return response.success
    
    # ==================== Expression ====================
    
    async def look_at(self, x: float, y: float) -> bool:
        """
        Point head toward target.
        
        Args:
            x: Horizontal position (-1.0 to 1.0, 0 = center)
            y: Vertical position (-1.0 to 1.0, 0 = center)
        """
        response = await self._send_command("look_at", {"x": x, "y": y})
        return response.success
    
    async def express(self, emotion: str) -> bool:
        """
        Set animatronic + LED expression.
        
        Args:
            emotion: idle, listening, thinking, speaking, happy, curious, alert, tired, sleeping, greeting
        """
        response = await self._send_command("express", {"emotion": emotion})
        return response.success
    
    # ==================== Audio ====================
    
    async def say(self, text: str) -> bool:
        """
        Speak text via TTS.
        
        Args:
            text: Text to speak
        """
        response = await self._send_command("say", {"text": text})
        return response.success
    
    async def play(self, path: str) -> bool:
        """
        Play audio file.
        
        Args:
            path: Path to audio file
        """
        response = await self._send_command("play", {"path": path})
        return response.success
    
    async def set_volume(self, volume: int, channel: str = "voice") -> bool:
        """
        Set volume level.
        
        Args:
            volume: 0-100
            channel: voice or music
        """
        response = await self._send_command("set_volume", {
            "volume": max(0, min(100, volume)),
            "channel": channel
        })
        return response.success
    
    # ==================== Sensors ====================
    
    async def get_camera_frame(self) -> Optional[bytes]:
        """
        Get current camera frame.
        
        Returns:
            Raw frame bytes or None
        """
        response = await self._send_command("get_camera")
        if response.success and response.data.get("frame"):
            import base64
            return base64.b64decode(response.data["frame"])
        return None
    
    async def get_faces(self) -> List[Dict]:
        """
        Get detected faces.
        
        Returns:
            List of face dicts with id, bbox, confidence
        """
        response = await self._send_command("get_faces")
        if response.success:
            return response.data.get("faces", [])
        return []
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get full vehicle status.
        
        Returns:
            Status dict with battery, thermal, position, safety, etc.
        """
        response = await self._send_command("get_status")
        if response.success:
            return response.data
        return {}
    
    # ==================== System ====================
    
    async def identify(self, name: str) -> bool:
        """
        Identify this driver to Vehicle OS.
        
        Args:
            name: Driver name (e.g., "Luna", "RemoteOperator")
        """
        response = await self._send_command("identify", {"name": name})
        return response.success
    
    async def ping(self) -> float:
        """
        Ping server (keepalive).
        
        Returns:
            Server timestamp
        """
        response = await self._send_command("ping")
        if response.success:
            return response.data.get("pong", 0)
        return 0
    
    async def shutdown(self) -> bool:
        """Request Vehicle OS shutdown"""
        response = await self._send_command("shutdown")
        return response.success


# ==================== Convenience Functions ====================

async def connect(socket_path: Optional[str] = None) -> DriverClient:
    """
    Quick connect to Vehicle OS.
    
    Usage:
        client = await vehicle_os.connect()
        await client.move("forward", 0.5)
    """
    client = DriverClient()
    await client.connect(socket_path)
    return client


# Example usage
async def main():
    """Example driver script"""
    logging.basicConfig(level=logging.INFO)
    
    client = DriverClient()
    
    if not await client.connect():
        print("Failed to connect to Vehicle OS")
        return
    
    try:
        # Identify ourselves
        await client.identify("ExampleDriver")
        
        # Get status
        status = await client.get_status()
        print(f"Battery: {status.get('battery_percent', '?')}%")
        print(f"Thermal: {status.get('thermal', '?')}")
        
        # Express greeting
        await client.express("greeting")
        await asyncio.sleep(1)
        
        # Say hello
        await client.say("Hello! I am Luna.")
        
        # Move a little
        await client.move("forward", 0.3)
        await asyncio.sleep(2)
        await client.stop()
        
        # Return to idle
        await client.express("idle")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
