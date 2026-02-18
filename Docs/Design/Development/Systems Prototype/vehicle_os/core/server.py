"""
Vehicle OS Server
=================

Unix socket server that accepts driver connections and dispatches commands
to subsystems. Enforces safety layer and manages idle behavior.
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional, Callable, Dict, Any

from vehicle_os.core.types import (
    Command, Response, Status, Emotion, Direction,
    SafetyState, ThermalStatus
)
from vehicle_os.core.config import VehicleConfig, get_config

logger = logging.getLogger(__name__)


class VehicleServer:
    """
    Main Vehicle OS server.
    
    Handles:
    - Unix socket for driver connection
    - Command dispatch to subsystems
    - Safety watchdog
    - Idle behavior when no driver connected
    """
    
    def __init__(self, config: Optional[VehicleConfig] = None):
        self.config = config or get_config()
        self.status = Status()
        self.running = False
        self.driver_writer: Optional[asyncio.StreamWriter] = None
        self.last_command_time = time.time()
        self.start_time = time.time()
        
        # Subsystem references (set during init)
        self._motion = None
        self._animatronics = None
        self._leds = None
        self._audio = None
        self._sensors = None
        self._navigation = None
        
        # Command handlers
        self._handlers: Dict[str, Callable] = {
            # Movement
            "move": self._handle_move,
            "stop": self._handle_stop,
            "go_to": self._handle_go_to,
            "go_home": self._handle_go_home,
            
            # Expression
            "look_at": self._handle_look_at,
            "express": self._handle_express,
            
            # Audio
            "say": self._handle_say,
            "play": self._handle_play,
            "set_volume": self._handle_set_volume,
            
            # Sensors
            "get_camera": self._handle_get_camera,
            "get_faces": self._handle_get_faces,
            "get_status": self._handle_get_status,
            
            # System
            "ping": self._handle_ping,
            "identify": self._handle_identify,
            "shutdown": self._handle_shutdown,
        }
    
    async def start(self):
        """Start the Vehicle OS server"""
        logger.info("Starting Vehicle OS...")
        
        # Remove stale socket
        socket_path = self.config.server.socket_path
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        
        # Initialize subsystems
        await self._init_subsystems()
        
        # Start server
        self.running = True
        server = await asyncio.start_unix_server(
            self._handle_connection,
            path=socket_path
        )
        
        logger.info(f"Vehicle OS listening on {socket_path}")
        
        # Start background tasks
        asyncio.create_task(self._safety_watchdog())
        asyncio.create_task(self._idle_behavior())
        asyncio.create_task(self._status_updater())
        
        async with server:
            await server.serve_forever()
    
    async def stop(self):
        """Stop the Vehicle OS server"""
        logger.info("Stopping Vehicle OS...")
        self.running = False
        
        # Safe shutdown
        await self._handle_stop(Command(action="stop"))
        await self._handle_express(Command(action="express", params={"emotion": "sleeping"}))
        
        # Cleanup
        socket_path = self.config.server.socket_path
        if os.path.exists(socket_path):
            os.unlink(socket_path)
    
    async def _init_subsystems(self):
        """Initialize all hardware subsystems"""
        logger.info("Initializing subsystems...")
        
        # Import here to allow graceful degradation if hardware not present
        try:
            from vehicle_os.subsystems.motion import MotionController
            self._motion = MotionController(self.config)
            await self._motion.init()
            logger.info("  Motion controller: OK")
        except Exception as e:
            logger.warning(f"  Motion controller: FAILED ({e})")
            self._motion = None
        
        try:
            from vehicle_os.subsystems.animatronics import AnimatronicsController
            self._animatronics = AnimatronicsController(self.config)
            await self._animatronics.init()
            logger.info("  Animatronics: OK")
        except Exception as e:
            logger.warning(f"  Animatronics: FAILED ({e})")
            self._animatronics = None
        
        try:
            from vehicle_os.subsystems.leds import LEDController
            self._leds = LEDController(self.config)
            await self._leds.init()
            logger.info("  LEDs: OK")
        except Exception as e:
            logger.warning(f"  LEDs: FAILED ({e})")
            self._leds = None
        
        try:
            from vehicle_os.subsystems.audio import AudioController
            self._audio = AudioController(self.config)
            await self._audio.init()
            logger.info("  Audio: OK")
        except Exception as e:
            logger.warning(f"  Audio: FAILED ({e})")
            self._audio = None
        
        try:
            from vehicle_os.subsystems.sensors import SensorController
            self._sensors = SensorController(self.config)
            await self._sensors.init()
            logger.info("  Sensors: OK")
        except Exception as e:
            logger.warning(f"  Sensors: FAILED ({e})")
            self._sensors = None
        
        try:
            from vehicle_os.subsystems.navigation import NavigationController
            self._navigation = NavigationController(self.config, self._motion, self._sensors)
            await self._navigation.init()
            logger.info("  Navigation: OK")
        except Exception as e:
            logger.warning(f"  Navigation: FAILED ({e})")
            self._navigation = None
        
        logger.info("Subsystem initialization complete")
    
    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming driver connection"""
        peer = writer.get_extra_info('peername') or "unknown"
        logger.info(f"Driver connecting from {peer}")
        
        # Only allow one driver at a time
        if self.driver_writer is not None:
            logger.warning("Rejecting connection - driver already connected")
            error = Response(success=False, error="Another driver is already connected")
            writer.write(json.dumps(error.to_dict()).encode() + b'\n')
            await writer.drain()
            writer.close()
            return
        
        self.driver_writer = writer
        self.status.driver_connected = True
        self.last_command_time = time.time()
        
        # Welcome expression
        await self._handle_express(Command(action="express", params={"emotion": "greeting"}))
        
        try:
            while self.running:
                data = await reader.readline()
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode())
                    command = Command.from_dict(msg)
                    self.last_command_time = time.time()
                    
                    response = await self._dispatch_command(command)
                    
                    writer.write(json.dumps(response.to_dict()).encode() + b'\n')
                    await writer.drain()
                    
                except json.JSONDecodeError as e:
                    error = Response(success=False, error=f"Invalid JSON: {e}")
                    writer.write(json.dumps(error.to_dict()).encode() + b'\n')
                    await writer.drain()
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            logger.info("Driver disconnected")
            self.driver_writer = None
            self.status.driver_connected = False
            self.status.driver_name = ""
            
            # Return to idle
            await self._handle_express(Command(action="express", params={"emotion": "idle"}))
            writer.close()
    
    async def _dispatch_command(self, command: Command) -> Response:
        """Dispatch command to appropriate handler"""
        handler = self._handlers.get(command.action)
        
        if handler is None:
            return Response(
                success=False,
                error=f"Unknown action: {command.action}",
                id=command.id
            )
        
        # Safety check before executing
        safety_ok, safety_msg = await self._safety_check(command)
        if not safety_ok:
            return Response(
                success=False,
                error=f"Safety block: {safety_msg}",
                id=command.id
            )
        
        try:
            result = await handler(command)
            return Response(
                success=True,
                data=result if isinstance(result, dict) else {},
                id=command.id
            )
        except Exception as e:
            logger.error(f"Command failed: {command.action} - {e}")
            return Response(
                success=False,
                error=str(e),
                id=command.id
            )
    
    async def _safety_check(self, command: Command) -> tuple[bool, str]:
        """Check if command is safe to execute"""
        # Always allow status queries
        if command.action in ("get_status", "get_camera", "get_faces", "ping"):
            return True, ""
        
        # Check thermal limits
        if self.status.thermal == ThermalStatus.CRITICAL:
            if command.action in ("move", "go_to"):
                return False, "Thermal critical - movement disabled"
        
        # Check battery
        if self.status.battery_percent <= self.config.safety.battery_critical_percent:
            if command.action in ("move", "go_to", "play"):
                return False, "Battery critical - limited functions"
        
        # Check obstacle for movement
        if command.action == "move":
            direction = command.params.get("direction", "")
            if direction == "forward" and self.status.safety == SafetyState.OBSTACLE_DETECTED:
                return False, "Obstacle detected ahead"
        
        # Check emergency stop
        if self.status.safety == SafetyState.EMERGENCY_STOP:
            if command.action in ("move", "go_to"):
                return False, "Emergency stop active"
        
        return True, ""
    
    # ==================== Command Handlers ====================
    
    async def _handle_move(self, cmd: Command) -> dict:
        """Handle move command"""
        direction = cmd.params.get("direction", "stop")
        speed = cmd.params.get("speed", 0.5)
        
        if self._motion:
            await self._motion.move(Direction(direction), speed)
        
        return {"direction": direction, "speed": speed}
    
    async def _handle_stop(self, cmd: Command) -> dict:
        """Handle stop command"""
        if self._motion:
            await self._motion.stop()
        return {}
    
    async def _handle_go_to(self, cmd: Command) -> dict:
        """Handle navigation to GPS coordinates"""
        lat = cmd.params.get("lat")
        lon = cmd.params.get("lon")
        
        if self._navigation and lat and lon:
            asyncio.create_task(self._navigation.go_to(lat, lon))
        
        return {"navigating_to": {"lat": lat, "lon": lon}}
    
    async def _handle_go_home(self, cmd: Command) -> dict:
        """Handle return to hub"""
        if self._navigation:
            asyncio.create_task(self._navigation.go_home())
        
        return {"navigating_to": "home"}
    
    async def _handle_look_at(self, cmd: Command) -> dict:
        """Handle head movement"""
        x = cmd.params.get("x", 0)
        y = cmd.params.get("y", 0)
        
        if self._animatronics:
            await self._animatronics.look_at(x, y)
        
        return {"looking_at": {"x": x, "y": y}}
    
    async def _handle_express(self, cmd: Command) -> dict:
        """Handle expression change"""
        emotion_str = cmd.params.get("emotion", "idle")
        emotion = Emotion(emotion_str)
        
        self.status.current_emotion = emotion
        
        if self._animatronics:
            await self._animatronics.express(emotion)
        
        if self._leds:
            await self._leds.express(emotion)
        
        return {"emotion": emotion.value}
    
    async def _handle_say(self, cmd: Command) -> dict:
        """Handle text-to-speech"""
        text = cmd.params.get("text", "")
        
        if self._audio and text:
            # Set speaking expression while talking
            await self._handle_express(Command(action="express", params={"emotion": "speaking"}))
            await self._audio.say(text)
            # Return to previous expression
            await self._handle_express(Command(action="express", params={"emotion": "idle"}))
        
        return {"said": text}
    
    async def _handle_play(self, cmd: Command) -> dict:
        """Handle audio playback"""
        path = cmd.params.get("path", "")
        
        if self._audio and path:
            await self._audio.play(path)
        
        return {"playing": path}
    
    async def _handle_set_volume(self, cmd: Command) -> dict:
        """Handle volume change"""
        volume = cmd.params.get("volume", 50)
        channel = cmd.params.get("channel", "voice")
        
        if self._audio:
            await self._audio.set_volume(channel, volume)
        
        return {"volume": volume, "channel": channel}
    
    async def _handle_get_camera(self, cmd: Command) -> dict:
        """Handle camera frame request"""
        if self._sensors:
            frame = await self._sensors.get_camera_frame()
            # Return base64 encoded for JSON transport
            import base64
            return {"frame": base64.b64encode(frame).decode() if frame else None}
        return {"frame": None}
    
    async def _handle_get_faces(self, cmd: Command) -> dict:
        """Handle face detection request"""
        if self._sensors:
            faces = await self._sensors.get_faces()
            return {"faces": [{"id": f.id, "bbox": f.bbox, "confidence": f.confidence} for f in faces]}
        return {"faces": []}
    
    async def _handle_get_status(self, cmd: Command) -> dict:
        """Handle status request"""
        return self.status.to_dict()
    
    async def _handle_ping(self, cmd: Command) -> dict:
        """Handle ping (keepalive)"""
        return {"pong": time.time()}
    
    async def _handle_identify(self, cmd: Command) -> dict:
        """Handle driver identification"""
        name = cmd.params.get("name", "unknown")
        self.status.driver_name = name
        logger.info(f"Driver identified as: {name}")
        return {"identified": name}
    
    async def _handle_shutdown(self, cmd: Command) -> dict:
        """Handle shutdown request"""
        logger.info("Shutdown requested by driver")
        asyncio.create_task(self.stop())
        return {"shutting_down": True}
    
    # ==================== Background Tasks ====================
    
    async def _safety_watchdog(self):
        """Monitor safety conditions"""
        while self.running:
            try:
                # Update thermal status
                if self._sensors:
                    temps = await self._sensors.get_temperatures()
                    self.status.cpu_temp = temps.get("cpu", 0)
                    self.status.enclosure_temp = temps.get("enclosure", 0)
                    self.status.battery_temp = temps.get("battery", 0)
                    
                    # Determine thermal state
                    max_temp = max(self.status.cpu_temp, self.status.enclosure_temp)
                    if max_temp >= self.config.safety.cpu_temp_critical:
                        self.status.thermal = ThermalStatus.CRITICAL
                    elif max_temp >= self.config.safety.cpu_temp_warning:
                        self.status.thermal = ThermalStatus.HOT
                    elif max_temp >= self.config.safety.enclosure_temp_warning:
                        self.status.thermal = ThermalStatus.WARM
                    else:
                        self.status.thermal = ThermalStatus.NORMAL
                
                # Check obstacle distance
                if self._sensors:
                    distance = await self._sensors.get_obstacle_distance()
                    if distance < self.config.safety.min_obstacle_distance:
                        if self.status.safety == SafetyState.OK:
                            self.status.safety = SafetyState.OBSTACLE_DETECTED
                            # Auto-stop if moving forward
                            if self._motion:
                                await self._motion.stop()
                    else:
                        if self.status.safety == SafetyState.OBSTACLE_DETECTED:
                            self.status.safety = SafetyState.OK
                
                # Check battery
                if self._sensors:
                    battery = await self._sensors.get_battery()
                    self.status.battery_percent = battery.get("percent", 100)
                    self.status.battery_voltage = battery.get("voltage", 25.2)
                    
                    if self.status.battery_percent <= self.config.safety.battery_critical_percent:
                        if self.status.safety == SafetyState.OK:
                            self.status.safety = SafetyState.LOW_BATTERY
                            # Auto return home
                            if self._navigation:
                                logger.warning("Battery critical - returning to hub")
                                asyncio.create_task(self._navigation.go_home())
                
            except Exception as e:
                logger.error(f"Safety watchdog error: {e}")
            
            await asyncio.sleep(0.5)
    
    async def _idle_behavior(self):
        """Manage idle behavior when no driver connected or commands received"""
        while self.running:
            try:
                time_since_command = time.time() - self.last_command_time
                
                # Enter idle if driver times out
                if self.status.driver_connected:
                    if time_since_command > self.config.safety.driver_timeout_seconds:
                        if self.status.current_emotion != Emotion.IDLE:
                            logger.info("Driver timeout - entering idle")
                            await self._handle_stop(Command(action="stop"))
                            await self._handle_express(Command(action="express", params={"emotion": "idle"}))
                
                # Idle animations when not driven
                if not self.status.driver_connected or self.status.current_emotion == Emotion.IDLE:
                    # Subtle ear twitch every 10-20 seconds
                    if self._animatronics:
                        await self._animatronics.idle_animation()
                
            except Exception as e:
                logger.error(f"Idle behavior error: {e}")
            
            await asyncio.sleep(5.0)
    
    async def _status_updater(self):
        """Update status fields"""
        while self.running:
            self.status.uptime = time.time() - self.start_time
            await asyncio.sleep(1.0)


# Entry point for standalone running
async def main():
    logging.basicConfig(level=logging.INFO)
    server = VehicleServer()
    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
