"""
Navigation Controller
=====================

Handles autonomous navigation:
- GPS waypoint navigation
- Obstacle avoidance
- Path planning
- Return-to-hub
"""

import asyncio
import logging
import math
from typing import Optional, List, Tuple
from enum import Enum

from vehicle_os.core.types import Position, Direction
from vehicle_os.core.config import VehicleConfig

logger = logging.getLogger(__name__)


class NavState(Enum):
    """Navigation states"""
    IDLE = "idle"
    NAVIGATING = "navigating"
    AVOIDING_OBSTACLE = "avoiding_obstacle"
    ARRIVED = "arrived"
    FAILED = "failed"


class NavigationController:
    """
    Autonomous navigation using GPS and obstacle avoidance.
    
    Uses simple waypoint navigation with reactive obstacle avoidance.
    Not a full SLAM implementation - relies on GPS for localization.
    """
    
    def __init__(self, config: VehicleConfig, motion, sensors):
        self.config = config
        self._motion = motion
        self._sensors = sensors
        
        self._state = NavState.IDLE
        self._target: Optional[Position] = None
        self._waypoints: List[Position] = []
        self._nav_task: Optional[asyncio.Task] = None
        
        self._initialized = False
    
    async def init(self):
        """Initialize navigation"""
        self._initialized = True
        logger.info("Navigation controller initialized")
    
    async def go_to(self, lat: float, lon: float):
        """
        Navigate to GPS coordinates.
        
        Args:
            lat: Target latitude
            lon: Target longitude
        """
        # Cancel any existing navigation
        if self._nav_task:
            self._nav_task.cancel()
        
        self._target = Position(lat=lat, lon=lon)
        self._state = NavState.NAVIGATING
        
        logger.info(f"Navigating to ({lat}, {lon})")
        
        # Start navigation task
        self._nav_task = asyncio.create_task(self._navigation_loop())
    
    async def go_home(self):
        """Navigate back to hub"""
        home = self.config.navigation
        await self.go_to(home.home_lat, home.home_lon)
    
    async def stop(self):
        """Stop navigation"""
        if self._nav_task:
            self._nav_task.cancel()
        
        self._state = NavState.IDLE
        self._target = None
        
        if self._motion:
            await self._motion.stop()
    
    @property
    def state(self) -> NavState:
        return self._state
    
    @property
    def is_navigating(self) -> bool:
        return self._state == NavState.NAVIGATING
    
    async def _navigation_loop(self):
        """Main navigation loop"""
        try:
            while self._state == NavState.NAVIGATING and self._target:
                # Get current position
                current = await self._sensors.get_position()
                
                # Check if arrived
                distance = self._haversine_distance(
                    current.lat, current.lon,
                    self._target.lat, self._target.lon
                )
                
                if distance < self.config.navigation.waypoint_radius:
                    logger.info("Arrived at destination")
                    self._state = NavState.ARRIVED
                    await self._motion.stop()
                    break
                
                # Check for obstacles
                obstacle_dist = await self._sensors.get_obstacle_distance()
                
                if obstacle_dist < self.config.safety.min_obstacle_distance:
                    # Obstacle avoidance
                    self._state = NavState.AVOIDING_OBSTACLE
                    await self._avoid_obstacle()
                    self._state = NavState.NAVIGATING
                    continue
                
                # Calculate heading to target
                target_heading = self._bearing(
                    current.lat, current.lon,
                    self._target.lat, self._target.lon
                )
                
                # Get current heading from IMU/GPS
                current_heading = current.heading
                
                # Calculate turn needed
                heading_error = self._normalize_angle(target_heading - current_heading)
                
                # Determine movement
                if abs(heading_error) > 20:  # Need to turn
                    # Turn toward target
                    if heading_error > 0:
                        await self._motion.move(Direction.SPIN_RIGHT, 0.3)
                    else:
                        await self._motion.move(Direction.SPIN_LEFT, 0.3)
                else:
                    # Heading is close enough, move forward
                    # Slow down when obstacle in slow zone
                    if obstacle_dist < self.config.safety.slow_zone_distance:
                        speed = 0.3
                    else:
                        speed = 0.5
                    
                    await self._motion.move(Direction.FORWARD, speed)
                
                await asyncio.sleep(0.1)  # 10Hz control loop
                
        except asyncio.CancelledError:
            logger.info("Navigation cancelled")
            self._state = NavState.IDLE
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            self._state = NavState.FAILED
        finally:
            if self._motion:
                await self._motion.stop()
    
    async def _avoid_obstacle(self):
        """
        Simple reactive obstacle avoidance.
        
        Strategy: Stop, turn away from obstacle, proceed.
        """
        logger.info("Avoiding obstacle")
        
        # Stop
        await self._motion.stop()
        await asyncio.sleep(0.2)
        
        # Check which way is clearer (TODO: use depth image)
        # For now, just turn right
        await self._motion.move(Direction.SPIN_RIGHT, 0.3)
        await asyncio.sleep(1.0)  # Turn ~90 degrees
        
        # Move forward briefly
        await self._motion.move(Direction.FORWARD, 0.3)
        await asyncio.sleep(1.0)
        
        # Turn back toward original heading
        await self._motion.move(Direction.SPIN_LEFT, 0.3)
        await asyncio.sleep(0.5)
        
        await self._motion.stop()
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS points in meters.
        
        Uses Haversine formula for great-circle distance.
        """
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_phi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate bearing from point 1 to point 2.
        
        Returns:
            Bearing in degrees (0 = North, 90 = East)
        """
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)
        
        x = math.sin(delta_lambda) * math.cos(phi2)
        y = (math.cos(phi1) * math.sin(phi2) -
             math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda))
        
        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360
    
    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to -180 to 180 range"""
        while angle > 180:
            angle -= 360
        while angle < -180:
            angle += 360
        return angle


class PersonFollower:
    """
    Follow a detected person at a comfortable distance.
    
    Uses depth camera to track person position and maintain distance.
    """
    
    def __init__(self, config: VehicleConfig, motion, sensors):
        self.config = config
        self._motion = motion
        self._sensors = sensors
        
        self._following = False
        self._target_distance = 1.5  # meters
        self._follow_task: Optional[asyncio.Task] = None
    
    async def start_following(self):
        """Start following the nearest detected person"""
        self._following = True
        self._follow_task = asyncio.create_task(self._follow_loop())
    
    async def stop_following(self):
        """Stop following"""
        self._following = False
        if self._follow_task:
            self._follow_task.cancel()
        if self._motion:
            await self._motion.stop()
    
    async def _follow_loop(self):
        """Main follow loop"""
        try:
            while self._following:
                # Get person position from camera
                person = await self._sensors.get_person_position()
                
                if person is None:
                    # Lost person - stop and wait
                    await self._motion.stop()
                    await asyncio.sleep(0.2)
                    continue
                
                x, y, distance = person
                
                # Calculate movement
                if distance > self._target_distance + 0.5:
                    # Too far - move forward
                    speed = min(0.5, (distance - self._target_distance) / 2)
                    
                    # Adjust heading based on x position
                    if abs(x) > 0.2:  # Person not centered
                        if x > 0:
                            await self._motion.move(Direction.RIGHT, speed)
                        else:
                            await self._motion.move(Direction.LEFT, speed)
                    else:
                        await self._motion.move(Direction.FORWARD, speed)
                
                elif distance < self._target_distance - 0.3:
                    # Too close - back up
                    await self._motion.move(Direction.BACKWARD, 0.2)
                
                else:
                    # Good distance - just track heading
                    if abs(x) > 0.2:
                        if x > 0:
                            await self._motion.move(Direction.SPIN_RIGHT, 0.2)
                        else:
                            await self._motion.move(Direction.SPIN_LEFT, 0.2)
                    else:
                        await self._motion.stop()
                
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            pass
        finally:
            if self._motion:
                await self._motion.stop()
