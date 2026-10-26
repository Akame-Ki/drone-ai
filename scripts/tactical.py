"""Tactical view for control.py: synthetic FPV HUD, ToF "lidar" scope and 3D flight path.

The CoDrone EDU has no camera: the FPV is drawn from the IMU / range / position data.
The lidar is built from the single front range sensor: each reading is placed in the world
at the drone's position + heading, so turning on the spot (Q/E) sweeps the room.
"""
import math
import time
import tkinter as tk
from collections import deque

from hud import enum_name

BG, G, G2, G3, G4 = "#030a06", "#39ff7a", "#1fae52", "#0e5a2c", "#0a2414"
AMB, RED = "#ffb547", "#ff4545"
FONT = "Consolas"

RANGE_MAX_CM = 150
LIDAR_MAX_PTS = 1500
LIDAR_FADE_S = 90
TRAIL_MAX_PTS = 4000
TRAIL_MIN_STEP_M = 0.01
SCOPE_RANGE_M = 2.0
TOF_FOV_DEG = 25

# label, action, column, row, width in columns
KEYPAD = [("Q", "yaw_left", 0, 0, 1), ("W", "forward", 1, 0, 1), ("E", "yaw_right", 2, 0, 1),
          ("A", "left", 0, 1, 1), ("S", "backward", 1, 1, 1), ("D", "right", 2, 1, 1),
          ("SHF", "up", 3.2, 0, 1.3), ("CTL", "down", 3.2, 1, 1.3)]


def mix(c1, c2, f):
    """Blend two #rrggbb colors, f=0 -> c1, f=1 -> c2."""
    f = max(0.0, min(1.0, f))
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(p + (q - p) * f) for p, q in zip(a, b))


def clip_line(x1, y1, x2, y2, box):
    """Liang-Barsky: the part of the segment inside box (x0, y0, x1, y1), or None."""
    bx0, by0, bx1, by1 = box
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1), (-dy, y1 - by0), (dy, by1 - y1)):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy


def frame(c, x, y, w, h, title=None):
    c.create_rectangle(x, y, x + w, y + h, fill=BG, outline=G4)
    k = 14
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        c.create_line(cx, cy + dy * k, cx, cy, cx + dx * k, cy, fill=G2, width=2)
    if title:
        c.create_text(x + 12, y + 12, anchor="w", fill=G2, font=(FONT, 9, "bold"), text=f"▌{title}")


class TacticalView:
    def __init__(self, telemetry, pilot):
        self.tel = telemetry
        self.pilot = pilot
        self.trail = deque(maxlen=TRAIL_MAX_PTS)   # (t, x, y, z) in m
        self.lidar = deque(maxlen=LIDAR_MAX_PTS)   # (t, x, y, z) in m, world frame
        self.recent = deque()                      # last second of positions, for speeds
        self.distance = 0.0
        self.az, self.el = math.radians(-35), math.radians(28)
        self.box3d = (0, 0, 0, 0)
        self.sweep = 0.0
        self._last_t = None
        self._drag = None
        self._manual_until = 0.0

    def clear(self):
        self.trail.clear()
        self.lidar.clear()
        self.distance = 0.0

    # ---------- data ----------

    def ingest(self, v):
        if not self.tel.linked(v) or v["t_state"] == self._last_t:
            return
        self._last_t = v["t_state"]
        t = self.tel.now()
        p = (v["x"], v["y"], v["z"])
        if not self.trail:
            self.trail.append((t, *p))
        else:
            step = math.dist(self.trail[-1][1:], p)
            if step >= TRAIL_MIN_STEP_M:
                self.trail.append((t, *p))
                self.distance += step
        self.recent.append((t, *p))
        while self.recent and self.recent[0][0] < t - 1:
            self.recent.popleft()
        d = v["front_cm"]
        if 0 < d < RANGE_MAX_CM:
            psi = math.radians(v["yaw"])
            self.lidar.append((t, p[0] + d / 100 * math.cos(psi), p[1] + d / 100 * math.sin(psi), p[2]))

    def speeds(self):
        """(ground speed, vertical speed) in cm/s over the last second."""
        if len(self.recent) < 2:
            return 0.0, 0.0
        (t0, x0, y0, z0), (t1, x1, y1, z1) = self.recent[0], self.recent[-1]
        if t1 - t0 < 0.2:
            return 0.0, 0.0
        return math.hypot(x1 - x0, y1 - y0) / (t1 - t0) * 100, (z1 - z0) / (t1 - t0) * 100

    # ---------- mouse (3D view) ----------

    def on_press(self, e):
        x, y, w, h = self.box3d
        self._drag = (e.x, e.y) if x <= e.x <= x + w and y <= e.y <= y + h else None

    def on_drag(self, e):
        if not self._drag:
            return
        dx, dy = e.x - self._drag[0], e.y - self._drag[1]
        self._drag = (e.x, e.y)
        self.az -= dx * 0.01
        self.el = max(0.05, min(1.45, self.el + dy * 0.01))
        self._manual_until = time.time() + 5

    # ---------- layout ----------

    def draw(self, c, W, H, v):
        self.ingest(v)
        linked = self.tel.linked(v)
        c.create_rectangle(0, 0, W, H, fill=BG, outline="")
        gap = 10
        right_w = max(360, int(W * 0.33))
        fw = W - right_w - gap
        console_h = 190
        fh = H - console_h - gap
        lh = (H - gap) // 2
        self.draw_fpv(c, 0, 0, fw, fh, v, linked)
        self.draw_console(c, 0, fh + gap, fw, console_h, v, linked)
        self.draw_lidar(c, fw + gap, 0, right_w, lh, v, linked)
        self.draw_3d(c, fw + gap, lh + gap, right_w, H - lh - gap, v, linked)

    # ---------- FPV ----------

    def draw_fpv(self, c, x, y, w, h, v, linked):
        frame(c, x, y, w, h)
        for sy in range(int(y) + 2, int(y + h), 4):  # scanlines
            c.create_line(x + 1, sy, x + w - 1, sy, fill="#05120a")
        cx, cy = x + w / 2, y + h / 2
        R = min(w, h) * 0.40
        blink = int(time.time() * 2) % 2 == 0

        roll_deg = v.get("roll", 0) if linked else 0
        pitch = v.get("pitch", 0) if linked else 0
        roll = math.radians(roll_deg)
        ux, uy = math.cos(roll), math.sin(roll)
        nx, ny = -math.sin(roll), math.cos(roll)
        ppd = h / 50  # pixels per degree of pitch

        # pitch ladder (same convention as the basic horizon: nose up moves the horizon down)
        for a in range(-90, 91, 10):
            d = (pitch - a) * ppd
            if abs(d) > R:
                continue
            px, py = cx + nx * d, cy + ny * d
            if a == 0:
                for s in (-1, 1):
                    c.create_line(px + s * ux * 70, py + s * uy * 70, px + s * ux * w * 0.42,
                                  py + s * uy * w * 0.42, fill=G, width=2)
                continue
            inner, outer = 45, 115
            dash = () if a > 0 else (6, 4)
            tick = 10 if a > 0 else -10
            for s in (-1, 1):
                x1, y1 = px + s * ux * inner, py + s * uy * inner
                x2, y2 = px + s * ux * outer, py + s * uy * outer
                c.create_line(x1, y1, x2, y2, fill=G2, width=2, dash=dash)
                c.create_line(x2, y2, x2 + nx * tick, y2 + ny * tick, fill=G2, width=2)
                c.create_text(x2 + s * ux * 18, y2 + s * uy * 18, fill=G2, font=(FONT, 9), text=str(abs(a)))

        # roll scale, rotates with the horizon; fixed pointer on top
        rr = R * 0.95
        for t in (-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60):
            phi = math.radians(t + roll_deg)
            ln = 14 if t % 30 == 0 else 8
            c.create_line(cx + rr * math.sin(phi), cy - rr * math.cos(phi),
                          cx + (rr + ln) * math.sin(phi), cy - (rr + ln) * math.cos(phi),
                          fill=G if t == 0 else G2, width=2)
        c.create_polygon(cx, cy - rr + 2, cx - 7, cy - rr + 14, cx + 7, cy - rr + 14, fill=G, outline="")

        # boresight
        c.create_line(cx - 44, cy, cx - 20, cy, cx - 10, cy + 12, cx, cy, cx + 10, cy + 12,
                      cx + 20, cy, cx + 44, cy, fill=AMB, width=2)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=AMB, outline="")

        gs, vs = self.speeds()
        self.draw_heading_tape(c, cx, y + 22, w * 0.5, v, linked)
        alt = v.get("bottom_cm", 999)
        if not linked:
            alt = 0
        elif alt >= RANGE_MAX_CM:
            alt = v.get("z", 0) * 100
        self.draw_vtape(c, x + w - 70, cy, h * 0.5, alt, "AGL CM", f"VS {vs:+4.0f}", right=True)
        self.draw_vtape(c, x + 70, cy, h * 0.5, gs, "GS CM/S", "", right=False)

        # corner blocks
        f = (FONT, 10)
        state = enum_name(v.get("flight")) if linked else "----"
        move = enum_name(v.get("movement")) if linked else "----"
        c.create_text(x + 16, y + 20, anchor="w", fill=G, font=(FONT, 11, "bold"), text="CDE-1 // SYNTH-FPV")
        c.create_text(x + 16, y + 38, anchor="w", fill=G2, font=f, text=f"MODE  {state.upper()}")
        c.create_text(x + 16, y + 54, anchor="w", fill=G2, font=f, text=f"MOVE  {move.upper()}")

        now = self.tel.now()
        c.create_text(x + w - 16, y + 20, anchor="e", fill=G, font=(FONT, 11, "bold"),
                      text=f"T+ {int(now // 60):02d}:{now % 60:04.1f}")
        if blink:
            c.create_text(x + w - 16, y + 38, anchor="e", fill=RED, font=(FONT, 10, "bold"), text="● REC")
        c.create_text(x + w - 16, y + 54, anchor="e", fill=G2 if linked else RED, font=f,
                      text="DATALINK OK" if linked else "DATALINK LOST")

        batt = v.get("battery", 0) if linked else 0
        bcol = G if batt > 50 else AMB if batt > 20 else RED
        c.create_text(x + 16, y + h - 54, anchor="w", fill=bcol, font=f, text=f"BATT {batt:3d}%")
        c.create_rectangle(x + 100, y + h - 60, x + 200, y + h - 48, outline=G3)
        c.create_rectangle(x + 101, y + h - 59, x + 101 + 98 * batt / 100, y + h - 49, fill=bcol, outline="")
        level = enum_name(v.get("speed")) if linked else "-"
        headless = "ON" if enum_name(v.get("headless")) == "Headless" else "OFF"
        c.create_text(x + 16, y + h - 34, anchor="w", fill=G2, font=f,
                      text=f"PWR {self.pilot.power:3d}  LVL {level}  HDLS {headless}")
        if linked:
            c.create_text(x + w - 16, y + h - 54, anchor="e", fill=G2, font=f,
                          text=f"X {v['x']:+.2f}  Y {v['y']:+.2f}  Z {v['z']:+.2f} M")
            fwd = "----" if v["front_cm"] >= RANGE_MAX_CM else f"{v['front_cm']:4.0f}"
            c.create_text(x + w - 16, y + h - 34, anchor="e", fill=G2, font=f,
                          text=f"FWD RNG {fwd} CM   TEMP {v['temp_c']:4.1f}C")

        # pilot message under the heading tape
        msg = self.pilot.current_message()
        if msg:
            c.create_text(cx, y + 78, fill=AMB, font=(FONT, 12, "bold"), text=f"> {msg.upper()}")

        # warnings, flashing
        warnings = []
        if not linked:
            warnings.append(("SIGNAL LOST", RED))
        if self.pilot.emergency:
            warnings.append(("EMERGENCY STOP", RED))
        if linked:
            if v["front_cm"] < 50:
                warnings.append((f"OBSTACLE {v['front_cm']:.0f} CM", RED))
            if batt < 20:
                warnings.append(("LOW BATTERY", AMB))
            for flag in v.get("sensor_flags", []) + v.get("state_flags", []):
                if not flag.startswith("RF_"):
                    warnings.append((flag.upper(), AMB))
        for i, (text, col) in enumerate(warnings[:3]):
            wy = cy + R * 0.55 + i * 30
            tw = len(text) * 9 + 24
            inverse = blink and col == RED  # red warnings flash, always readable
            c.create_rectangle(cx - tw / 2, wy - 12, cx + tw / 2, wy + 12, outline=col, width=2,
                               fill=col if inverse else BG)
            c.create_text(cx, wy, fill=BG if inverse else col, font=(FONT, 12, "bold"), text=text)

    def draw_heading_tape(self, c, cx, ty, tw, v, linked):
        hdg = (-v.get("yaw", 0)) % 360 if linked else 0  # yaw is + to the left, a compass goes clockwise
        span = 70
        left = cx - tw / 2
        c.create_line(left, ty + 20, left + tw, ty + 20, fill=G3)
        for deg in range(int(hdg - span / 2) - 1, int(hdg + span / 2) + 2):
            if deg % 5:
                continue
            sx = cx + (deg - hdg) * tw / span
            if not left <= sx <= left + tw:
                continue
            big = deg % 10 == 0
            c.create_line(sx, ty + 20, sx, ty + (8 if big else 14), fill=G2)
            if deg % 30 == 0:
                c.create_text(sx, ty, fill=G2, font=(FONT, 9), text=f"{deg % 360:03d}")
        c.create_rectangle(cx - 26, ty + 24, cx + 26, ty + 42, fill=BG, outline=G)
        c.create_text(cx, ty + 33, fill=G, font=(FONT, 11, "bold"), text=f"{hdg:03.0f}")
        c.create_polygon(cx, ty + 21, cx - 5, ty + 25, cx + 5, ty + 25, fill=G, outline="")

    def draw_vtape(self, c, tx, cy, th, value, label, sub, right):
        span = 100  # units visible on the tape
        top = cy - th / 2
        c.create_line(tx, top, tx, top + th, fill=G3)
        side = 1 if right else -1
        for u in range(int(value - span / 2) - 1, int(value + span / 2) + 2):
            if u % 10:
                continue
            sy = cy - (u - value) * th / span
            if not top <= sy <= top + th:
                continue
            c.create_line(tx, sy, tx + side * (10 if u % 20 == 0 else 5), sy, fill=G2)
            if u % 20 == 0:
                c.create_text(tx + side * 16, sy, anchor="w" if right else "e", fill=G2, font=(FONT, 9), text=str(u))
        bx = tx - side * 6
        c.create_polygon(bx, cy, bx - side * 10, cy - 11, bx - side * 56, cy - 11,
                         bx - side * 56, cy + 11, bx - side * 10, cy + 11, fill=BG, outline=G)
        c.create_text(bx - side * 33, cy, fill=G, font=(FONT, 11, "bold"), text=f"{value:4.0f}")
        c.create_text(tx, top - 14, fill=G2, font=(FONT, 9), text=label)
        if sub:
            c.create_text(tx, top + th + 14, fill=G2, font=(FONT, 9), text=sub)

    # ---------- console ----------

    def draw_console(self, c, x, y, w, h, v, linked):
        frame(c, x, y, w, h, "FLIGHT CONSOLE")
        status, col = self.pilot.status()
        col = {"#3fb950": G, "#f85149": RED, "#d29922": AMB}.get(col, G2)
        c.create_text(x + 16, y + 38, anchor="w", fill=col, font=(FONT, 16, "bold"), text=status)

        # keypad
        kx, ky, size, gap = x + 16, y + 60, 34, 5
        for label, action, col_i, row, span in KEYPAD:
            bx = kx + col_i * (size + gap)
            by = ky + row * (size + gap)
            bw = size * span + gap * (span - 1)
            on = action in self.pilot.held
            c.create_rectangle(bx, by, bx + bw, by + size, fill=G if on else BG, outline=G3)
            c.create_text(bx + bw / 2, by + size / 2, fill=BG if on else G2, font=(FONT, 10, "bold"), text=label)

        # stick indicators: left = yaw/throttle, right = roll/pitch (mode 2)
        r, p, yw, t = self.pilot.stick
        sx0 = kx + 4.7 * (size + gap)
        for i, (label, hx, hy) in enumerate((("YAW/THR", -yw, t), ("ROLL/PIT", r, p))):
            bx = sx0 + i * 92
            c.create_rectangle(bx, ky, bx + 73, ky + 73, outline=G3)
            c.create_line(bx + 36.5, ky, bx + 36.5, ky + 73, fill=G4)
            c.create_line(bx, ky + 36.5, bx + 73, ky + 36.5, fill=G4)
            dx, dy = bx + 36.5 + hx / 100 * 32, ky + 36.5 - hy / 100 * 32
            c.create_oval(dx - 5, dy - 5, dx + 5, dy + 5, fill=G, outline="")
            c.create_text(bx + 36.5, ky + 86, fill=G2, font=(FONT, 8), text=label)

        # power bar
        px0 = kx
        py0 = ky + 2 * (size + gap) + 14
        c.create_text(px0, py0, anchor="w", fill=G2, font=(FONT, 9), text="PWR")
        c.create_rectangle(px0 + 34, py0 - 7, px0 + 194, py0 + 7, outline=G3)
        c.create_rectangle(px0 + 35, py0 - 6, px0 + 35 + 158 * self.pilot.power / 100, py0 + 6,
                           fill=AMB if self.pilot.power > 60 else G, outline="")

        # event log
        lx = sx0 + 200
        c.create_text(lx, y + 38, anchor="w", fill=G2, font=(FONT, 9, "bold"), text="EVENT LOG")
        for i, (t_ev, text) in enumerate(list(self.pilot.log)[-7:]):
            c.create_text(lx, y + 58 + i * 15, anchor="w", fill=G if i == len(self.pilot.log) - 1 else G2,
                          font=(FONT, 9), text=f"[{int(t_ev // 60):02d}:{t_ev % 60:04.1f}] {text.upper()}")

        c.create_text(x + 16, y + h - 14, anchor="w", fill=G3, font=(FONT, 8),
                      text="SPC TAKEOFF/LAND  ESC E-STOP  +/- PWR  F1-3 LVL  ARROWS FLIP  "
                           "H HDLS  R RTH  L LED  C CLEAR MAP  TAB VIEW")

    # ---------- lidar ----------

    def draw_lidar(self, c, x, y, w, h, v, linked):
        frame(c, x, y, w, h, "LIDAR // ToF SWEEP")
        cx, cy = x + w / 2, y + 22 + (h - 44) / 2
        r = min(w, h - 50) / 2 - 8
        scale = r / SCOPE_RANGE_M
        for ring in (0.5, 1.0, 1.5, 2.0):
            rr = ring * scale
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=G4 if ring != 1.5 else G3)
            c.create_text(cx + rr * 0.71 + 4, cy - rr * 0.71 - 4, anchor="w", fill=G3, font=(FONT, 8), text=f"{ring:.1f}")
        c.create_line(cx - r, cy, cx + r, cy, fill=G4)
        c.create_line(cx, cy - r, cx, cy + r, fill=G4)

        # sweep beam (cosmetic)
        self.sweep = (self.sweep + 0.12) % (2 * math.pi)
        for i in range(10):
            a = self.sweep - i * 0.05
            c.create_line(cx, cy, cx + r * math.sin(a), cy - r * math.cos(a), fill=mix(G2, BG, i / 10))

        if linked:
            psi = math.radians(v["yaw"])
            px, py = v["x"], v["y"]
            now = self.tel.now()
            cos_p, sin_p = math.cos(psi), math.sin(psi)
            for t, wx, wy, _ in self.lidar:
                age = now - t
                if age > LIDAR_FADE_S:
                    continue
                dx, dy = wx - px, wy - py
                fwd = dx * cos_p + dy * sin_p
                left = -dx * sin_p + dy * cos_p
                if fwd * fwd + left * left > SCOPE_RANGE_M ** 2:
                    continue
                sx, sy = cx - left * scale, cy - fwd * scale
                s = 2 if age > 3 else 3
                c.create_rectangle(sx - s, sy - s, sx + s, sy + s, outline="",
                                   fill=mix(G, BG, age / LIDAR_FADE_S * 0.85))

            # current front sensor cone
            d = v["front_cm"] / 100
            hit = d < RANGE_MAX_CM / 100
            reach = (d if hit else RANGE_MAX_CM / 100) * scale
            half = math.radians(TOF_FOV_DEG / 2)
            for s in (-1, 1):
                c.create_line(cx, cy, cx + s * reach * math.sin(half), cy - reach * math.cos(half),
                              fill=AMB if hit else G3, dash=() if hit else (3, 3))
            if hit:
                c.create_oval(cx - 5, cy - reach - 5, cx + 5, cy - reach + 5, outline=AMB, width=2)

        c.create_polygon(cx, cy - 9, cx - 6, cy + 6, cx, cy + 3, cx + 6, cy + 6, fill=G, outline="")
        fwd_txt = "----" if not linked or v["front_cm"] >= RANGE_MAX_CM else f"{v['front_cm']:.0f}"
        agl_txt = "----" if not linked or v["bottom_cm"] >= RANGE_MAX_CM else f"{v['bottom_cm']:.0f}"
        c.create_text(x + 12, y + h - 12, anchor="w", fill=G2, font=(FONT, 9),
                      text=f"PTS {len(self.lidar)}  FWD {fwd_txt}  AGL {agl_txt} CM")
        c.create_text(x + w - 12, y + h - 12, anchor="e", fill=G3, font=(FONT, 8), text="TURN Q/E TO SCAN")

    # ---------- 3D path ----------

    def draw_3d(self, c, x, y, w, h, v, linked):
        self.box3d = (x, y, w, h)
        frame(c, x, y, w, h, "FLIGHT PATH // 3D")
        if time.time() > self._manual_until:
            self.az += 0.01

        now = self.tel.now()
        pts = [(px, py, pz) for _, px, py, pz in self.trail]
        scan = [(t, p) for t, *p in list(self.lidar)[-600:] if now - t <= LIDAR_FADE_S]
        cur = (v["x"], v["y"], v["z"]) if linked else (pts[-1] if pts else (0.0, 0.0, 0.0))
        allp = pts + [p for _, p in scan] + [cur, (0.0, 0.0, 0.0)]
        xs, ys, zs = zip(*allp)
        mid = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
        radius = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0) / 2 * 1.3
        vx, vy = x + w / 2, y + 22 + (h - 50) / 2
        scale = min(w, h - 50) * 0.45 / radius
        D = radius * 4
        ca, sa, ce, se = math.cos(self.az), math.sin(self.az), math.cos(self.el), math.sin(self.el)

        def proj(p):
            px, py, pz = p[0] - mid[0], p[1] - mid[1], p[2] - mid[2]
            a = px * ca - py * sa
            b = px * sa + py * ca
            depth = a * ce + pz * se
            up = pz * ce - a * se
            f = D / (D + depth)
            return vx - b * scale * f, vy - up * scale * f

        box = (x + 2, y + 24, x + w - 2, y + h - 24)

        def line(p1, p2, **kw):
            seg = clip_line(*p1, *p2, box)
            if seg:
                c.create_line(*seg, **kw)

        def inside(sx, sy):
            return box[0] <= sx <= box[2] and box[1] <= sy <= box[3]

        # ground grid on z = 0
        step = 0.5
        g = math.ceil(radius / step) * step
        gx0, gy0 = round(mid[0] / step) * step, round(mid[1] / step) * step
        n = int(g / step)
        for i in range(-n, n + 1):
            k = i * step
            line(proj((gx0 + k, gy0 - g, 0)), proj((gx0 + k, gy0 + g, 0)), fill=G4)
            line(proj((gx0 - g, gy0 + k, 0)), proj((gx0 + g, gy0 + k, 0)), fill=G4)

        # takeoff pad
        pad = [proj((sx * 0.1, sy * 0.1, 0)) for sx, sy in ((-1, -1), (-1, 1), (1, 1), (1, -1))]
        c.create_polygon(*[n for p in pad for n in p], outline=G2, fill="")
        hx, hy = proj((0, 0, 0))
        c.create_text(hx, hy, fill=G2, font=(FONT, 8, "bold"), text="H")

        # lidar points
        for t, p in scan:
            sx, sy = proj(p)
            if inside(sx, sy):
                c.create_rectangle(sx - 1, sy - 1, sx + 1, sy + 1, outline="",
                                   fill=mix(AMB, BG, 0.3 + (now - t) / LIDAR_FADE_S * 0.6))

        # trail: older = dimmer, with drop lines to the ground
        if len(pts) >= 2:
            sp = [proj(p) for p in pts]
            chunks = 10
            size = max(2, len(sp) // chunks + 1)
            for ci, i0 in enumerate(range(0, len(sp) - 1, size - 1)):
                seg = sp[i0:i0 + size]
                if len(seg) >= 2:
                    c.create_line(*[n for p in seg for n in p], fill=mix(G3, G, i0 / len(sp)), width=2)
            for i in range(0, len(pts), max(1, len(pts) // 25)):
                line(sp[i], proj((pts[i][0], pts[i][1], 0)), fill=G4)

        # drone marker + heading
        dx, dy = proj(cur)
        gx, gy = proj((cur[0], cur[1], 0))
        c.create_line(dx, dy, gx, gy, fill=G3, dash=(3, 3))
        c.create_oval(gx - 4, gy - 2, gx + 4, gy + 2, outline=G3)
        if linked:
            psi = math.radians(v["yaw"])
            ax, ay = proj((cur[0] + 0.3 * math.cos(psi), cur[1] + 0.3 * math.sin(psi), cur[2]))
            c.create_line(dx, dy, ax, ay, fill=AMB, width=2, arrow="last")
        c.create_polygon(dx, dy - 7, dx + 7, dy, dx, dy + 7, dx - 7, dy, fill=G, outline="")

        # axes gizmo
        ox, oy = x + 34, y + h - 40
        for label, vec in (("X", (1, 0, 0)), ("Y", (0, 1, 0)), ("Z", (0, 0, 1))):
            a = vec[0] * ca - vec[1] * sa
            b = vec[0] * sa + vec[1] * ca
            up = vec[2] * ce - a * se
            ex, ey = ox - b * 18, oy - up * 18
            c.create_line(ox, oy, ex, ey, fill=G2)
            c.create_text(ex + (ex - ox) * 0.4, ey + (ey - oy) * 0.4, fill=G2, font=(FONT, 8), text=label)

        c.create_text(x + w - 12, y + h - 12, anchor="e", fill=G2, font=(FONT, 9),
                      text=f"DIST {self.distance:.2f} M  PTS {len(pts)}")
        c.create_text(x + w - 12, y + 12, anchor="e", fill=G3, font=(FONT, 8),
                      text=f"AZ {math.degrees(self.az) % 360:03.0f}  EL {math.degrees(self.el):02.0f}  DRAG TO ROTATE")
