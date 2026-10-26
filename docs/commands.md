# CoDrone EDU — Python command reference

Library: `codrone_edu` **v2.10** (`pip install codrone-edu`). List pulled from the installed library itself, not only the docs, so it includes undocumented methods.
All methods are on `drone = Drone()`. `★` = not in the official docs page. `⚠` = deprecated alias.

Power values are -100..100 unless noted. Distances in cm by default. Angles in degrees.

---

## 1. Connection
| Command | What it does |
|---|---|
| `pair(portname=None)` | Connect to the controller over USB (auto-detect, or `'/dev/ttyACM0'` / `'COM3'`) |
| `connect(portname=None)` ★ | Same as pair |
| `open(portName=None)` ★ | Open the serial port only |
| `close()` | Close the connection |
| `disconnect()` ★ | Disconnect |
| `isOpen()` / `isConnected()` ★ | Port/link status |
| `ping(r,g,b)` ★ | Ping the drone (optionally flashes LED) |
| `check()` / `checkDetail()` ★ | Connection diagnostics |

## 2. Flight basics
| Command | What it does |
|---|---|
| `takeoff()` | Takes off to ~80 cm, hovers 1 s (height not changeable) |
| `land()` | Soft landing, resets flight variables |
| `emergency_stop()` | Kills motors immediately (it falls) |
| `stop_motors()` ★ | Stop motors |
| `hover(duration=0.01)` | Hover for N seconds |

## 3. Movement (distance-based, uses optical flow — fly over a lit, patterned floor)
| Command | What it does |
|---|---|
| `move_forward(distance, units='cm', speed=0.5)` | Units: cm, ft, in, m. Speed in m/s, max 2.0 |
| `move_backward(...)`, `move_left(...)`, `move_right(...)` | Same signature |
| `move_upward(...)`, `move_downward(...)` ★ | Vertical, same signature |
| `move_distance(x, y, z, velocity)` | Relative move in meters, axes combined. x=fwd, y=left, z=up |
| `send_absolute_position(x, y, z, velocity, heading, rotVel)` | Go to absolute pos from takeoff point. x,y ±10 m, z 0–1.5 m |
| `set_waypoint()` ★ | Save current position to a waypoint list |
| `goto_waypoint(waypoint, velocity)` ★ | Fly back to a saved waypoint |

## 4. Movement (power/time-based)
| Command | What it does |
|---|---|
| `set_roll(p)` / `set_pitch(p)` / `set_yaw(p)` / `set_throttle(p)` | Set flight variable (no movement yet) |
| `move(duration=None)` | Apply the set variables for N s (or forever) |
| `get_move_values()` | Returns `[roll, pitch, yaw, throttle]` |
| `reset_move_values(attempts=3)` | All variables to 0 |
| `go(direction, power=50, duration=1)` ★ | `"forward"`, `"backward"`, `"left"`, `"right"`, `"up"`, `"down"` |
| `speed_change(speed_level=1)` ★ | Drone speed level (1–3) |
| `get_control_speed()` ★ | Current speed level |
| `print_move_values()` ⚠, `reset_move()` ⚠ | Old names |

## 5. Turning
| Command | What it does |
|---|---|
| `turn(power=50, seconds=None)` | + left, − right |
| `turn_degree(degree=90, timeout=3, p_value=10)` | Absolute heading vs. initial heading (−180..180), P-controller |
| `turn_direction(degree=90, timeout=3, p_value=10)` ★ | Relative turn |
| `turn_left(degree=90)` / `turn_right(degree=90)` | Gyro turns |

## 6. Pre-made sequences
| Command | What it does |
|---|---|
| `flip(direction='back')` | `back`, `front`, `left`, `right`. Needs >50 % battery, wait 3–4 s after |
| `circle(speed=75, direction=1)` | 1 left, −1 right |
| `circle_turn(speed=30, seconds=1, direction=1)` ★ | Circle while turning |
| `spiral(speed=50, seconds=5, direction=1)` | Downward spiral |
| `square(speed=60, seconds=1, direction=1)` | |
| `triangle(speed=60, seconds=1, direction=1)` | |
| `triangle_turn(speed=60, seconds=2, direction=1)` ★ | |
| `sway(speed=30, seconds=2, direction=1)` | |

## 7. Automatic behaviors (sensor loops)
| Command | What it does |
|---|---|
| `avoid_wall(timeout=2, distance=70)` | Fly forward until wall at X cm |
| `keep_distance(timeout=2, distance=50)` | Follow/keep distance from object |
| `detect_wall(distance=50)` | True if something closer than X cm |

## 8. Trim / calibration
| Command | What it does |
|---|---|
| `set_trim(roll, pitch)` | Fix drift (saved on drone). `sleep(1)` before takeoff |
| `get_trim()` | `[roll, pitch]` |
| `reset_trim()` | Back to 0 |
| `reset_gyro()` | Reset roll/pitch/yaw angles (`reset_sensor()` ⚠) |
| `sendClearBias()` ★ | Recalibrate IMU (drone flat & still) |
| `set_initial_pressure()` | Reference for barometer height |

## 9. Sensors
**Position:** `get_pos_x/y/z(unit='cm')`, `get_position_data()` → `[time, x, y, z]`
**Range (ToF):** `get_front_range(unit)`, `get_bottom_range(unit)`, `get_height(unit)` — max 150 cm, 999 = out of range
**Optical flow:** `get_flow_velocity_x/y(unit)`, `get_flow_data()` ★ (`get_flow_x/y` ⚠)
**IMU:** `get_accel_x/y/z()`, `get_angle_x/y/z()`, `get_angular_speed_x/y/z()`, `get_motion_data()` ★, `get_raw_motion_data()` ★, `get_x/y/z_gyro()` ★ (`get_x_accel`, `get_x_angle`… ⚠)
**Barometer:** `get_pressure(unit='Pa')`, `get_elevation(unit='m')` ★, `height_from_pressure(b=0, m=9.34)`, `get_drone_temperature(unit='C')` (`get_temperature` ⚠), `get_altitude_data()` ★
**Color (bottom sensors):** `get_colors()` → `[front, back]` names, `get_front_color()`, `get_back_color()`, `get_color_data()`, `detect_colors(data)` ★
**Custom color training:** `new_color_data(label, data, dataset)`, `append_color_data(...)`, `load_color_data(dataset, show_graph)`, `predict_colors(data)`, `reset_classifier()` ★, `print_num_data(label, dataset)` ★
**Bulk:** `get_sensor_data()` → list of 31 values (all of the above in one call), `get_range_data()` ★

## 10. State / info
| Command | What it does |
|---|---|
| `get_battery()` | % |
| `get_flight_state()` | Ready, TakeOff, Flight, Landing… |
| `get_movement_state()` | Ready, Hovering, ReturnHome |
| `get_system_state()` ★ | System mode |
| `get_state_data()` ★ | Full state packet |
| `get_error_data(delay=0.2, print_error=True)` | Sensor/calibration/battery errors |
| `get_flight_time()` ★, `get_takeoff_count()` ★, `get_landing_count()` ★, `get_accident_count()` ★ | Lifetime counters |
| `get_information_data()` ★, `get_cpu_id_data()` ★, `get_address_data()` ★ | Firmware/hardware IDs |
| `headless_change(mode)` ★ | Headless mode on/off |
| `control_change(mode)` ★ | Flight control mode (Attitude / Position / Manual…) |

## 11. LEDs
| Command | What it does |
|---|---|
| `set_drone_LED(r, g, b, brightness)` | RGB 0–255, brightness 0–100 |
| `set_controller_LED(r, g, b, brightness)` | |
| `set_drone_LED_mode(r, g, b, mode, speed)` ★ | Effects: solid, dimming, flicker, rainbow… |
| `set_controller_LED_mode(r, g, b, mode, speed)` ★ | |
| `drone_LED_off()` / `controller_LED_off()` | |

## 12. Sound / vibration
| Command | What it does |
|---|---|
| `drone_buzzer(note, ms)` / `controller_buzzer(note, ms)` | Hz or `Note.A4` |
| `start_drone_buzzer(note)` / `stop_drone_buzzer()` | Background tone |
| `start_controller_buzzer(note)` / `stop_controller_buzzer()` | |
| `drone_buzzer_sequence(kind)` ★ / `controller_buzzer_sequence(kind)` ★ | Preset melodies |
| `sendVibrator(on, off, total)` ★ | Controller vibration (ms) |

## 13. Controller input (use the controller as a gamepad)
`h_pressed()`, `p_pressed()`, `s_pressed()`, `power_pressed()`, `l1_pressed()`, `l2_pressed()`, `r1_pressed()`, `r2_pressed()`, `up/down/left/right_arrow_pressed()`, `get_button_data()`, `get_left_joystick_x/y()`, `get_right_joystick_x/y()`, `get_joystick_data()`

## 14. Controller screen (128×64 mono)
Canvas (PIL): `controller_create_canvas()`, `controller_draw_point/line/rectangle/square/ellipse/arc/chord/polygon/string/string_align(...)`, `controller_draw_canvas(image)`, `controller_preview_canvas()`, `controller_draw_image(pixel_list)`, `get_image_data(file)`, `controller_clear_screen()`
Direct: `sendDisplayClearAll()`, `sendDisplayClear(...)`, `sendDisplayInvert(...)`, `sendDisplayDrawPoint/Line/Rect/Circle/String/StringAlign(...)`, `sendBacklight(on)`

## 15. Low-level protocol (★, building blocks for new commands)
| Command | What it does |
|---|---|
| `sendControl(roll, pitch, yaw, throttle)` | One raw stick packet |
| `sendControlWhile(roll, pitch, yaw, throttle, timeMs)` | Hold sticks for N ms |
| `sendControlPosition(x, y, z, vel, heading, rotVel)` | Raw position command |
| `sendTakeOff()`, `sendLanding()`, `sendStop()` | Raw flight events |
| `sendFlightEvent(FlightEvent.X)` | TakeOff, Landing, Stop, FlipFront/Rear/Left/Right, Return, ResetHeading, Shot, UnderAttack |
| `sendFlip(mode)` | Raw flip |
| `sendCommand(CommandType.X, option)` | Generic command: Stop, ModeControlFlight, Headless, ControlSpeed, ClearBias, ClearTrim, FlightEvent, SetDefault, Trim, ClearCounter… |
| `sendMotor(m0, m1, m2, m3)` / `sendMotorSingle(target, value)` / `set_motor_speed(fr, br, bl, fl)` | **Raw motor power, no stabilization. Props off for testing.** |
| `sendTrim(roll, pitch, yaw, throttle)`, `sendClearTrim()`, `sendClearBias()` | |
| `sendHeadless(mode)`, `sendModeControlFlight(mode)` | |
| `sendLightManual/LightModeColor/LightEventColor/LightDefaultColor(...)` | Full LED protocol |
| `sendBuzzer/BuzzerHz/BuzzerScale/BuzzerMute(...)` (+ `Reserve` variants) | Full buzzer protocol |
| `sendWeight(weight)` | Tell drone about payload weight |
| `sendLostConnection(timeNeutral, timeLanding, timeStop)` | **Failsafe timings when the link drops** |
| `sendPairing(...)`, `sendControlleLinkMode()`, `sendSetDefault(device)` | Pairing / reset (careful) |
| `sendRequest(DeviceType, DataType)` | Ask the drone for any data packet |
| `setEventHandler(DataType, fn)` / `add_callback(name, fn)` | Run your function when a packet arrives |
| `transfer(header, data)` | Send any raw packet |

---

## Creating new commands

The drone firmware is closed: everything runs on your PC, and a "new command" is a Python function that combines what the protocol already supports. Three levels:

### Level 1 — combine existing commands (90 % of cases)
```python
from codrone_edu.drone import Drone
from codrone_edu.protocol import *
import time

class MyDrone(Drone):
    def safe_takeoff(self, min_batt=40):
        b = self.get_battery()
        if b < min_batt:
            raise RuntimeError(f"Battery too low: {b}%")
        self.takeoff()

    def zigzag(self, n=4, power=40, t=0.6):
        for i in range(n):
            roll = 30 if i % 2 else -30
            self.sendControlWhile(roll, power, 0, 0, int(t * 1000))
        self.hover(1)

    def climb_to(self, target_cm=120, power=40, timeout=5):
        end = time.time() + timeout
        while self.get_height() < target_cm and time.time() < end:
            self.sendControl(0, 0, 0, power)
            time.sleep(0.05)
        self.hover(1)

drone = MyDrone()
drone.pair()
drone.safe_takeoff()
drone.zigzag()
drone.land()
drone.close()
```

### Level 2 — use protocol commands the docs don't expose
```python
    def headless(self, on=True):
        self.sendCommand(CommandType.Headless,
                         (Headless.Headless if on else Headless.Normal).value)

    def return_home(self):
        self.sendFlightEvent(FlightEvent.Return)

    def failsafe(self, neutral_ms=1000, land_ms=3000, stop_ms=8000):
        # what the drone does if the controller link drops
        self.sendLostConnection(neutral_ms, land_ms, stop_ms)
```

### Level 3 — raw packets + listening to data
```python
    def send_raw(self, data_type, payload, to=DeviceType.Drone):
        h = Header()
        h.dataType = data_type
        h.length = payload.getSize()
        h.from_ = DeviceType.Base
        h.to_ = to
        return self.transfer(h, payload)

    def on_battery(self, fn):
        # fn(data) is called every time a State packet arrives
        self.setEventHandler(DataType.State, fn)
        self.sendRequest(DeviceType.Drone, DataType.State)
```

### Limits
- New commands can only use what the drone firmware understands (`CommandType`, `FlightEvent`, `DataType` enums in `codrone_edu/protocol.py`).
- No on-drone code: if the USB/radio link drops, your script stops controlling it. Set `sendLostConnection()` and always wrap flights in `try/except KeyboardInterrupt: drone.emergency_stop()`.
- `sendMotor` bypasses stabilization. Test props-off.
- The Robolink website is the same library compiled to WebAssembly (Pyodide; the code checks `sys.platform == 'emscripten'`). Running locally is the same API, just without the browser.

Source: library v2.10 introspection, https://docs.robolink.com/docs/CoDroneEDU/Python/Function-Documentation
