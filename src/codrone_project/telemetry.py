"""Background poller for every data stream the CoDrone EDU sends, with history for graphs.

The drone pushes each packet into the Drone's *_data lists when it arrives; this class
asks for them on a schedule and copies them into one flat dict.
"""
import threading
import time
from collections import deque

from codrone_edu.protocol import (DataType, DeviceType,
                                  ErrorFlagsForSensor, ErrorFlagsForState)

HISTORY_S = 30     # seconds of history kept for graphs
STALE_S = 2.0      # no state packet for this long = link lost
MEDIUM_EVERY = 5   # ticks between medium-rate requests
SLOW_EVERY = 40    # ticks between slow-rate requests

FAST = (DataType.State, DataType.Motion, DataType.Range,
        DataType.Position, DataType.Altitude, DataType.RawFlow)
MEDIUM = (DataType.CardColor, DataType.RawMotion, DataType.Joystick, DataType.Error)
SLOW = (DataType.Trim, DataType.Count)

HISTORY_KEYS = ("roll", "pitch", "yaw", "gyro_roll", "gyro_pitch", "gyro_yaw",
                "accel_x", "accel_y", "accel_z", "bottom_cm", "range_height_cm", "z_cm",
                "front_cm", "x", "y", "flow_x", "flow_y", "battery", "pressure_pa", "temp_c")


def flag_names(value, enum):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return []
    return [f.name for f in enum if f.value and value & f.value == f.value]


def color_name(value):
    # ColorCard enum once a packet arrived, 0 before
    return value.name if hasattr(value, "name") else "Unknown"


class Telemetry:
    def __init__(self, drone, poll_s=0.1):
        self.drone = drone
        self.poll_s = poll_s
        self.lock = threading.Lock()
        self.values = {}
        self.history = {k: deque() for k in HISTORY_KEYS}
        self.running = False
        self._tick = 0

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        time.sleep(self.poll_s * 2)

    def now(self):
        return time.time() - self.drone.timeStartProgram

    def linked(self, values=None):
        v = self.values if values is None else values
        return bool(v) and self.now() - v.get("t_state", -1e9) < STALE_S

    def snapshot(self):
        """(values, history) copies that are safe to read from the UI thread."""
        with self.lock:
            return dict(self.values), {k: list(q) for k, q in self.history.items()}

    def _request(self, data_type, device=DeviceType.Drone):
        self.drone.sendRequest(device, data_type)
        time.sleep(0.01)

    def _loop(self):
        while self.running:
            try:
                self._poll()
            except Exception as e:  # serial hiccup: keep polling
                with self.lock:
                    self.values["error"] = str(e)
                time.sleep(0.5)
                continue
            time.sleep(self.poll_s)

    def _poll(self):
        k = self._tick
        self._tick += 1
        for dt in FAST:
            self._request(dt)
        if k % MEDIUM_EVERY == 0:
            for dt in MEDIUM:
                self._request(dt)
        if k % SLOW_EVERY == 0:
            for dt in SLOW:
                self._request(dt)
            self._request(DataType.Information)
            self._request(DataType.Information, DeviceType.Controller)
        self._update()

    def _update(self):
        d = self.drone
        s, m, r, p = d.state_data, d.motion_data, d.range_data, d.position_data
        a, f, rm, c = d.altitude_data, d.flow_data, d.raw_motion_data, d.color_data
        j, e, tr, cnt, info = d.joystick_data, d.error_data, d.trim_data, d.count_data, d.information_data
        v = {
            "t_state": s[0],
            "system": s[1], "flight": s[2], "control_mode": s[3], "headless": s[4],
            "orientation": s[5], "battery": s[6], "movement": s[7], "speed": s[8],
            "accel_x": m[1], "accel_y": m[2], "accel_z": m[3],
            "gyro_roll": m[4], "gyro_pitch": m[5], "gyro_yaw": m[6],
            "roll": m[7], "pitch": m[8], "yaw": m[9],
            "front_cm": r[1] / 10, "bottom_cm": r[2] / 10,            # mm -> cm
            "x": p[1], "y": p[2], "z": p[3], "z_cm": p[3] * 100,      # m
            "temp_c": a[1], "pressure_pa": a[2], "elevation_m": a[3],
            "range_height_cm": a[4] * 100,
            "flow_x": f[1], "flow_y": f[2],
            "raw_accel": rm[1:4], "raw_gyro": rm[4:7],
            "color_front": color_name(c[9]), "color_back": color_name(c[10]), "card": c[11],
            "hsvl_front": c[1:5], "hsvl_back": c[5:9],
            "rgb_front": c[12:15], "rgb_back": c[15:18],
            "joy_left": (j[1], j[2]), "joy_right": (j[5], j[6]),
            "joy_dirs": (j[3], j[7]), "buttons": list(d.button_data[1:]),
            "sensor_flags": flag_names(e[1], ErrorFlagsForSensor),
            "state_flags": flag_names(e[2], ErrorFlagsForState),
            "trim": tr[1:5],
            "flight_time": cnt[1], "takeoffs": cnt[2], "landings": cnt[3], "accidents": cnt[4],
            "drone_model": info[1], "drone_fw": info[2],
            "controller_model": info[3], "controller_fw": info[4],
        }
        now = self.now()
        with self.lock:
            self.values = v
            if self.linked(v):
                for key in HISTORY_KEYS:
                    q = self.history[key]
                    q.append((now, v[key]))
                    while q and q[0][0] < now - HISTORY_S:
                        q.popleft()
