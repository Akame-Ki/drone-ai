"""Fly the drone with the keyboard, with the HUD on screen.

Usage:
    python scripts/control.py                    # auto-detect the controller port
    python scripts/control.py COM5 --power 40    # stick power 1-100 (default 40)
    python scripts/control.py COM5 --advanced    # start in the tactical view

Keys (the window must have focus):
    W / S        forward / backward       Shift   up
    A / D        left / right             Ctrl    down
    Q / E        turn left / right        Space   takeoff / landing
    Esc          EMERGENCY STOP: motors off, the drone falls
    Tab          view: basic -> tactical (FPV, lidar, 3D path) -> graphs

Advanced:
    + / - / mouse wheel   stick power ±10 (10-100)
    F1 / F2 / F3          drone speed level 1-3 (firmware setting, 3 = very fast)
    Arrow keys            flip front / back / left / right (flying, battery >= 50 %)
    H                     headless mode on / off
    R                     return to the takeoff point
    L                     cycle the drone LED color
    C                     clear the lidar map and the 3D path
    Mouse drag            rotate the 3D path (tactical view)

Releasing every key = hover. If the window loses focus, all keys are released.
Closing the window while flying lands first.
"""
import argparse
import sys
import threading
import time
import tkinter as tk
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codrone_edu.drone import Drone
from codrone_edu.protocol import FlightEvent, Headless, ModeFlight
from codrone_project.telemetry import Telemetry
from hud import ACCENT, BAD, DIM, FG, MONO, OK, PANEL, SANS, WARN, Hud, enum_name
from tactical import TacticalView

KEYS = {
    "w": "forward", "s": "backward", "a": "left", "d": "right",
    "q": "yaw_left", "e": "yaw_right",
    "shift_l": "up", "shift_r": "up", "control_l": "down", "control_r": "down",
}
SEND_S = 0.05            # stick packets at 20 Hz
RELEASE_DEBOUNCE_MS = 40  # key auto-repeat can send release/press pairs
EVENT_TIMEOUT_S = 2.0     # how long to retry takeoff/landing commands
CLOSE_LAND_TIMEOUT_S = 6.0
AIRBORNE = (ModeFlight.TakeOff, ModeFlight.Flight)

POWER_STEP, POWER_MIN, POWER_MAX = 10, 10, 100
POWER_KEYS = {"plus": 1, "equal": 1, "kp_add": 1, "minus": -1, "kp_subtract": -1}
SPEED_KEYS = {"f1": 1, "f2": 2, "f3": 3}
FLIPS = {"up": ("front", FlightEvent.FlipFront), "down": ("back", FlightEvent.FlipRear),
         "left": ("left", FlightEvent.FlipLeft), "right": ("right", FlightEvent.FlipRight)}
FLIP_MIN_BATTERY = 50
FLIP_COOLDOWN_S = 4
MESSAGE_S = 3  # how long an action message stays on screen
LED_COLORS = [("white", (255, 255, 255)), ("red", (255, 0, 0)), ("green", (0, 255, 0)),
              ("blue", (0, 0, 255)), ("yellow", (255, 200, 0)), ("purple", (160, 0, 255)),
              ("off", (0, 0, 0))]


def lock_serial_writes(drone):
    """The library has no lock: telemetry requests and stick packets come from different threads."""
    lock = threading.Lock()
    transfer = drone.transfer

    def locked(header, data):
        with lock:
            return transfer(header, data)

    drone.transfer = locked


class Pilot:
    """Turns held keys into stick commands, sent while the drone is airborne."""

    def __init__(self, drone, telemetry, power):
        self.drone = drone
        self.tel = telemetry
        self.power = power
        self.held = set()
        self.stick = (0, 0, 0, 0)
        self.event = None        # "taking off" / "landing" while a command is in progress
        self.emergency = False
        self.running = False
        self.message = ("", 0.0)
        self.log = deque(maxlen=50)  # (mission time, text)
        self._abort = threading.Event()
        self._last_flip = 0.0
        self._led = 0

    def start(self):
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def flight_state(self):
        return self.tel.values.get("flight") if self.tel.linked() else None

    def _loop(self):
        while self.running:
            h, p = self.held, self.power
            roll = p * (("right" in h) - ("left" in h))
            pitch = p * (("forward" in h) - ("backward" in h))
            yaw = p * (("yaw_left" in h) - ("yaw_right" in h))
            throttle = p * (("up" in h) - ("down" in h))
            self.stick = (roll, pitch, yaw, throttle)
            if self.event is None and self.flight_state() in AIRBORNE:
                self.drone.sendControl(roll, pitch, yaw, throttle)
            time.sleep(SEND_S)

    def toggle_takeoff(self):
        if self.event:
            return
        state = self.flight_state()
        if state == ModeFlight.Ready:
            args = (self.drone.sendTakeOff, ModeFlight.TakeOff, "taking off")
        elif state in AIRBORNE:
            args = (self.drone.sendLanding, ModeFlight.Landing, "landing")
        else:
            return
        self.emergency = False
        threading.Thread(target=self._send_event, args=args, daemon=True).start()

    def _send_event(self, send, target, label):
        self.event = label
        self.say(label)
        self._abort.clear()
        self.drone.sendControl(0, 0, 0, 0)
        end = time.time() + EVENT_TIMEOUT_S
        while time.time() < end and not self._abort.is_set():
            if self.flight_state() == target:
                break
            send()
            time.sleep(0.1)
        self.event = None

    # ---------- advanced actions ----------

    def say(self, text):
        self.message = (text, time.time())
        self.log.append((self.tel.now(), text))

    def current_message(self):
        text, t = self.message
        return text if time.time() - t < MESSAGE_S else ""

    def change_power(self, direction):
        self.power = max(POWER_MIN, min(POWER_MAX, self.power + direction * POWER_STEP))
        self.say(f"power {self.power}")

    def set_speed_level(self, level):
        self.drone.speed_change(level)
        self.say(f"speed level {level}")

    def flip(self, key):
        name, event = FLIPS[key]
        if self.flight_state() != ModeFlight.Flight:
            return self.say("flip: only while flying")
        battery = self.tel.values.get("battery", 0)
        if battery < FLIP_MIN_BATTERY:
            return self.say(f"flip refused: battery {battery} % (needs {FLIP_MIN_BATTERY})")
        wait = FLIP_COOLDOWN_S - (time.time() - self._last_flip)
        if wait > 0:
            return self.say(f"flip: wait {wait:.0f} s")
        self._last_flip = time.time()
        self.drone.sendFlightEvent(event)
        self.say(f"flip {name}")

    def toggle_headless(self):
        on = enum_name(self.tel.values.get("headless")) != "Headless"
        self.drone.sendHeadless(Headless.Headless if on else Headless.Normal)
        self.say(f"headless {'on' if on else 'off'}")

    def return_home(self):
        if self.flight_state() not in AIRBORNE:
            return self.say("return home: only while flying")
        self.drone.sendFlightEvent(FlightEvent.Return)
        self.say("returning to takeoff point")

    def next_led(self):
        self._led = (self._led + 1) % len(LED_COLORS)
        name, (r, g, b) = LED_COLORS[self._led]
        self.drone.set_drone_LED(r, g, b, 100)
        self.say(f"LED {name}")

    def emergency_stop(self):
        self._abort.set()
        self.held.clear()
        self.emergency = True
        self.drone.emergency_stop()
        self.say("emergency stop")

    def shutdown(self):
        """Land if airborne, then stop sending."""
        if self.flight_state() in AIRBORNE:
            self._send_event(self.drone.sendLanding, ModeFlight.Landing, "landing")
            end = time.time() + CLOSE_LAND_TIMEOUT_S
            while time.time() < end and self.flight_state() not in (ModeFlight.Ready, None):
                time.sleep(0.1)
        self.running = False

    def status(self):
        if self.emergency:
            return "EMERGENCY STOP", BAD
        if self.event:
            return self.event.upper(), WARN
        state = self.flight_state()
        if state is None:
            return "NO LINK", BAD
        return enum_name(state).upper(), OK if state in AIRBORNE else FG


class ControlHud(Hud):
    BASIC_SIZE = "784x640"
    VIEWS = ("basic", "tactical", "graphs")

    PAD = [  # label, action, column, row, width in columns
        ("Q", "yaw_left", 0, 0, 1), ("W", "forward", 1, 0, 1), ("E", "yaw_right", 2, 0, 1),
        ("A", "left", 0, 1, 1), ("S", "backward", 1, 1, 1), ("D", "right", 2, 1, 1),
        ("SHIFT", "up", 3.3, 0, 1.6), ("CTRL", "down", 3.3, 1, 1.6),
    ]

    def __init__(self, root, telemetry, pilot, advanced=False):
        self.pilot = pilot
        self._down = set()
        self._pending = {}
        self.view = "tactical" if advanced else "basic"
        self.tactical = TacticalView(telemetry, pilot)
        super().__init__(root, telemetry, advanced)
        root.title("drone-ai control")
        root.bind("<KeyPress>", self.on_press)
        root.bind("<KeyRelease>", self.on_release)
        root.bind("<FocusOut>", lambda _e: self.release_all())
        root.bind("<MouseWheel>", lambda e: pilot.change_power(1 if e.delta > 0 else -1))
        self.c.bind("<ButtonPress-1>", self.tactical.on_press)
        self.c.bind("<B1-Motion>", self.tactical.on_drag)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle(self, _event=None):
        self.view = self.VIEWS[(self.VIEWS.index(self.view) + 1) % len(self.VIEWS)]
        self.advanced = self.view != "basic"
        self.root.geometry(self.ADVANCED_SIZE if self.advanced else self.BASIC_SIZE)
        return "break"

    def draw_advanced(self, v, history):
        if self.view == "tactical":
            self.tactical.draw(self.c, self.c.winfo_width(), self.c.winfo_height(), v)
        else:
            super().draw_advanced(v, history)

    def on_press(self, e):
        k = e.keysym.lower()  # Shift turns "w" into "W"
        if k in self._pending:
            self.root.after_cancel(self._pending.pop(k))
        first = k not in self._down
        self._down.add(k)
        if k == "escape":
            self.pilot.emergency_stop()
        elif k in KEYS:
            self.pilot.held.add(KEYS[k])
        elif k in POWER_KEYS:  # auto-repeat allowed
            self.pilot.change_power(POWER_KEYS[k])
        elif not first:  # the rest fires once per press
            return
        elif k == "space":
            self.pilot.toggle_takeoff()
        elif k in SPEED_KEYS:
            self.pilot.set_speed_level(SPEED_KEYS[k])
        elif k in FLIPS:
            self.pilot.flip(k)
        elif k == "h":
            self.pilot.toggle_headless()
        elif k == "r":
            self.pilot.return_home()
        elif k == "l":
            self.pilot.next_led()
        elif k == "c":
            self.tactical.clear()
            self.pilot.say("map cleared")

    def on_release(self, e):
        k = e.keysym.lower()
        if k in self._pending:
            self.root.after_cancel(self._pending[k])
        self._pending[k] = self.root.after(RELEASE_DEBOUNCE_MS, self._release, k)

    def _release(self, k):
        self._pending.pop(k, None)
        self._down.discard(k)
        if k in KEYS and not any(KEYS.get(o) == KEYS[k] for o in self._down):
            self.pilot.held.discard(KEYS[k])

    def release_all(self):
        self._down.clear()
        self.pilot.held.clear()

    def on_close(self):
        self.release_all()
        self.pilot.shutdown()
        self.root.destroy()

    def draw_overlay(self, v):
        self.tactical.ingest(v)  # keep recording the path and lidar in every view
        if self.view == "tactical":
            return
        c = self.c
        status, color = self.pilot.status()
        r, p, y, t = self.pilot.stick
        sticks = f"roll {r:+4}  pitch {p:+4}  yaw {y:+4}  thr {t:+4}"
        message = self.pilot.current_message()
        level = enum_name(v.get("speed", "?")) if self.tel.linked(v) else "?"
        headless = "on" if enum_name(v.get("headless")) == "Headless" else "off"
        if self.advanced:
            W = c.winfo_width()
            c.create_text(W / 2 - 320, 14, anchor="w", fill=color, font=(SANS, 12, "bold"), text=status)
            c.create_text(W / 2 - 160, 14, anchor="w", fill=DIM, font=(MONO, 9),
                          text=f"power {self.pilot.power}  level {level}  headless {headless}")
            c.create_text(W / 2 + 110, 14, anchor="w", fill=ACCENT, font=(SANS, 10, "bold"), text=message)
            return

        x0, y0, size, gap = 16, 430, 40, 6
        for label, action, col, row, span in self.PAD:
            x = x0 + col * (size + gap)
            y = y0 + row * (size + gap)
            on = action in self.pilot.held
            c.create_rectangle(x, y, x + size * span + gap * (span - 1), y + size,
                               fill=OK if on else PANEL, outline=DIM)
            c.create_text(x + (size * span + gap * (span - 1)) / 2, y + size / 2,
                          fill=PANEL if on else FG, font=(SANS, 10, "bold"), text=label)

        x1 = 300
        c.create_text(x1, y0 + 10, anchor="w", fill=color, font=(SANS, 14, "bold"), text=status)
        c.create_text(x1, y0 + 38, anchor="w", fill=FG, font=(MONO, 10),
                      text=f"{sticks}   power {self.pilot.power}")
        c.create_text(x1, y0 + 66, anchor="w", fill=ACCENT, font=(SANS, 11, "bold"), text=message)

        # power bar + modes
        y1 = y0 + 2 * (size + gap) + 18
        c.create_text(x0, y1, anchor="w", fill=DIM, font=(SANS, 9), text="POWER")
        bx, bw = x0 + 56, 220
        c.create_rectangle(bx, y1 - 9, bx + bw, y1 + 9, outline=DIM)
        c.create_rectangle(bx + 1, y1 - 8, bx + 1 + (bw - 2) * self.pilot.power / POWER_MAX, y1 + 8,
                           fill=WARN if self.pilot.power > 60 else OK, outline="")
        c.create_text(bx + bw / 2, y1, fill=FG, font=(SANS, 9, "bold"), text=str(self.pilot.power))
        c.create_text(x1, y1, anchor="w", fill=FG, font=(MONO, 10),
                      text=f"speed level {level}    headless {headless}")

        help_lines = [
            "SPACE takeoff / land     ESC emergency stop (drone falls)     TAB HUD view",
            "+ / - / wheel  power     F1 F2 F3  speed level     ARROWS  flip     H headless",
            "R return to takeoff point     L LED color",
        ]
        for i, line in enumerate(help_lines):
            c.create_text(x0, y1 + 28 + i * 18, anchor="w", fill=DIM, font=(SANS, 9), text=line)


def main():
    ap = argparse.ArgumentParser(description="Keyboard control with HUD")
    ap.add_argument("port", nargs="?", help="controller port, e.g. COM5 (auto-detect if omitted)")
    ap.add_argument("--power", type=int, default=40, help="stick power 1-100 (default 40)")
    ap.add_argument("--advanced", action="store_true", help="start in the advanced HUD view")
    args = ap.parse_args()

    drone = Drone()
    drone.pair(args.port)
    lock_serial_writes(drone)

    tel = Telemetry(drone)
    tel.start()
    pilot = Pilot(drone, tel, max(1, min(100, args.power)))
    pilot.start()

    root = tk.Tk()
    ControlHud(root, tel, pilot, advanced=args.advanced)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pilot.emergency_stop()
    finally:
        pilot.running = False
        tel.stop()
        drone.close()


if __name__ == "__main__":
    main()
