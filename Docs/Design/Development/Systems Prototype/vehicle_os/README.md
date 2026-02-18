# Vehicle OS

**Modular Robot Operating System**

Luna is the driver. Vehicle OS is the vehicle.

## Architecture

```
┌─────────────────────────────────────────┐
│  DRIVER (swappable)                     │
│  - Luna Engine (AI companion)           │
│  - Remote operator                      │
│  - Patrol script                        │
│  - Any other agent                      │
│           │                             │
│           ▼ Unix Socket API             │
├─────────────────────────────────────────┤
│  VEHICLE OS (persistent)                │
│  - Motion control                       │
│  - Sensor fusion                        │
│  - Navigation                           │
│  - Animatronics                         │
│  - LEDs                                 │
│  - Audio                                │
│  - Safety layer                         │
│           │                             │
│           ▼ Serial/I2C/GPIO             │
├─────────────────────────────────────────┤
│  HARDWARE                               │
│  - Jetson Orin Nano                     │
│  - Teensy 4.1                           │
│  - Motors, servos, sensors              │
└─────────────────────────────────────────┘
```

## Quick Start

### Start the Server

```bash
# Default
python -m vehicle_os

# With debug logging
python -m vehicle_os --debug

# Custom socket path
python -m vehicle_os --socket /tmp/my_robot.sock
```

### Connect as a Driver

```python
import asyncio
from vehicle_os import DriverClient

async def main():
    client = DriverClient()
    await client.connect()
    await client.identify("MyDriver")
    
    # Move
    await client.move("forward", 0.5)
    await asyncio.sleep(2)
    await client.stop()
    
    # Express
    await client.express("happy")
    
    # Speak
    await client.say("Hello world!")
    
    # Get status
    status = await client.get_status()
    print(f"Battery: {status['battery_percent']}%")
    
    await client.disconnect()

asyncio.run(main())
```

## API Commands

### Movement

| Command | Params | Description |
|---------|--------|-------------|
| `move` | `direction`, `speed` | Move in direction (forward, backward, left, right, spin_left, spin_right) |
| `stop` | - | Stop all movement |
| `go_to` | `lat`, `lon` | Navigate to GPS coordinates |
| `go_home` | - | Return to hub |

### Expression

| Command | Params | Description |
|---------|--------|-------------|
| `look_at` | `x`, `y` | Point head at position (-1 to 1 range) |
| `express` | `emotion` | Set expression (idle, listening, thinking, speaking, happy, curious, alert, tired, sleeping, greeting) |

### Audio

| Command | Params | Description |
|---------|--------|-------------|
| `say` | `text` | Speak text via TTS |
| `play` | `path` | Play audio file |
| `set_volume` | `volume`, `channel` | Set volume (0-100, voice or music) |

### Sensors

| Command | Params | Description |
|---------|--------|-------------|
| `get_camera` | - | Get camera frame (base64 JPEG) |
| `get_faces` | - | Get detected faces |
| `get_status` | - | Get full vehicle status |

### System

| Command | Params | Description |
|---------|--------|-------------|
| `ping` | - | Keepalive |
| `identify` | `name` | Identify this driver |
| `shutdown` | - | Shutdown Vehicle OS |

## Safety Layer

Vehicle OS enforces safety regardless of driver commands:

- **Collision avoidance**: Auto-stop when obstacle < 0.6m
- **Thermal protection**: Reduced operation when CPU > 75°C, shutdown > 85°C
- **Low battery**: Auto return-to-hub when < 10%
- **Tilt detection**: Stop if tilted > 30°
- **Driver timeout**: Enter idle if no commands for 30s

## Configuration

```python
from vehicle_os import VehicleConfig

config = VehicleConfig()

# Adjust safety thresholds
config.safety.min_obstacle_distance = 0.8  # meters
config.safety.battery_critical_percent = 15

# Set home position
config.navigation.home_lat = 33.3528
config.navigation.home_lon = -115.7292

# Audio settings
config.audio.voice_volume = 90
config.audio.tts_rate = 140
```

## Project Structure

```
vehicle_os/
├── __init__.py          # Package exports
├── __main__.py          # Entry point
├── core/
│   ├── types.py         # Enums, dataclasses
│   ├── config.py        # Configuration
│   ├── server.py        # Unix socket server
│   └── client.py        # Driver client
├── subsystems/
│   ├── motion.py        # Drivetrain control
│   ├── animatronics.py  # Servo expressions
│   ├── leds.py          # LED lighting
│   ├── audio.py         # TTS and playback
│   ├── sensors.py       # Camera, IMU, GPS
│   └── navigation.py    # Autonomous nav
├── utils/
│   ├── logging.py       # Log configuration
│   └── math.py          # Math utilities
└── examples/
    └── luna_driver.py   # Luna integration example
```

## Hardware Requirements

- **Compute**: NVIDIA Jetson Orin Nano 8GB
- **Microcontroller**: Teensy 4.1 (real-time motor/servo control)
- **Camera**: OAK-D Lite (depth + RGB + neural)
- **IMU**: BNO055
- **GPS**: NEO-M8N
- **Servos**: 8x (head, ears, tail, flippers) via PCA9685
- **Motors**: 4x geared DC motors with encoders
- **LEDs**: WS2812B strips (eyes, chest, tail, underglow)
- **Audio**: 15W horn + marine Bluetooth speaker

## License

Project Tapestry / Art Nest
