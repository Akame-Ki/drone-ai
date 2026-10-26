"""Live HUD of the drone telemetry in a window. Read-only: sends no flight command.

Usage:
    python scripts/hud.py                 # auto-detect the controller port
    python scripts/hud.py COM5            # or /dev/ttyACM0
    python scripts/hud.py COM5 --advanced # start in the advanced view

Tab switches between the basic and the advanced (all data + graphs) view.
"""
import math
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from codrone_edu.drone import Drone
from codrone_project.telemetry import HISTORY_S, Telemetry

RANGE_MAX_CM = 150

BG, PANEL, FG, DIM, GRID = "#101418", "#161b22", "#e6edf3", "#7d8590", "#262c34"
SKY, GROUND, ACCENT = "#2f6fae", "#7a5230", "#f2c84b"
OK, WARN, BAD = "#3fb950", "#d29922", "#f85149"
SERIES = ("#58a6ff", "#f778ba", "#3fb950", "#d29922")
MONO, SANS = "Consolas", "Segoe UI"

# title, unit, [(label, key)], fixed y range (values outside are clipped)
CHARTS = [
    ("Attitude", "°", [("roll", "roll"), ("pitch", "pitch")], None),
    ("Heading", "°", [("yaw", "yaw")], (-180, 180)),
    ("Gyro rate", "°/s", [("roll", "gyro_roll"), ("pitch", "gyro_pitch"), ("yaw", "gyro_yaw")], None),
    ("Accel", "", [("x", "accel_x"), ("y", "accel_y"), ("z", "accel_z")], None),
    ("Height", "cm", [("ToF", "bottom_cm"), ("alt ToF", "range_height_cm"), ("pos z", "z_cm")], (0, 200)),
    ("Front range", "cm", [("front", "front_cm")], (0, RANGE_MAX_CM)),
    ("Position", "m", [("x", "x"), ("y", "y")], None),
    ("Optical flow", "m", [("x", "flow_x"), ("y", "flow_y")], None),
    ("Battery", "%", [("battery", "battery")], (0, 100)),
    ("Pressure", "Pa", [("pressure", "pressure_pa")], None),
    ("Temperature", "°C", [("temp", "temp_c")], None),
]



def enum_name(v):
    return getattr(v, "name", str(v))


def fmt_range(cm):
    return "out" if cm is None or cm >= RANGE_MAX_CM else f"{cm:5.0f} cm"


def rgb_hex(rgb):
    try:
        return "#%02x%02x%02x" % tuple(max(0, min(255, int(n))) for n in rgb)
    except (TypeError, ValueError):
        return PANEL


def fmt_num(v, nd=1):
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) else str(v)


class Hud:
    HZ_R = 150  # artificial horizon radius
    BASIC_SIZE, ADVANCED_SIZE = "784x444", "1400x880"

    def __init__(self, root, telemetry, advanced=False):
        self.root = root
        self.tel = telemetry
        self.advanced = advanced
        root.title("drone-ai HUD")
        root.configure(bg=BG)
        root.geometry(self.ADVANCED_SIZE if advanced else self.BASIC_SIZE)
        root.bind("<Tab>", self.toggle)
        self.c = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.c.pack(fill="both", expand=True, padx=12, pady=12)
        self.refresh()

    def toggle(self, _event=None):
        self.advanced = not self.advanced
        self.root.geometry(self.ADVANCED_SIZE if self.advanced else self.BASIC_SIZE)
        return "break"  # keep Tab from moving the focus

    def refresh(self):
        values, history = self.tel.snapshot()
        self.c.delete("all")
        if self.advanced:
            self.draw_advanced(values, history)
        else:
            self.draw_basic(values)
        self.draw_overlay(values)
        self.c.after(100, self.refresh)

    def draw_overlay(self, values):
        """Hook for subclasses (control.py) to draw on top of the HUD."""

    # ---------- shared pieces ----------

    def draw_status(self, x, y, v, linked):
        c = self.c
        status, color = ("LINK", OK) if linked else ("NO DATA — drone off or not paired", BAD)
        c.create_text(x, y, anchor="w", fill=color, font=(SANS, 14, "bold"), text=status)
        if v.get("error"):
            c.create_text(x, y + 24, anchor="w", fill=BAD, font=(MONO, 9), text=v["error"][:60])

    def draw_horizon(self, cx, cy, r, v, linked):
        c = self.c
        # pitch shifts the line, roll rotates it
        roll = math.radians(v.get("roll", 0)) if linked else 0
        pitch = v.get("pitch", 0) if linked else 0
        off = max(-r, min(r, pitch * 3 * r / 150))  # 3 px per degree at r=150
        # ground = circle segment beyond the horizon line, along the normal (-sin, cos) of the roll
        nx, ny = -math.sin(roll), math.cos(roll)
        phi = math.degrees(math.atan2(-ny, nx))  # tk arc angles are counterclockwise, y up
        half = math.degrees(math.acos(off / r))
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=SKY, outline="")
        if half > 0:
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=phi - half, extent=min(2 * half, 359.9),
                         style=tk.CHORD, fill=GROUND, outline="")
        c.create_line(cx - r, cy, cx - r * 0.6, cy, fill=ACCENT, width=3)
        c.create_line(cx + r * 0.6, cy, cx + r, cy, fill=ACCENT, width=3)
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=ACCENT, outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=DIM, width=2)

    def draw_battery(self, x, y, w, batt):
        c = self.c
        bcol = OK if batt > 50 else WARN if batt > 20 else BAD
        c.create_rectangle(x, y, x + w, y + 20, outline=DIM)
        c.create_rectangle(x + 1, y + 1, x + 1 + (w - 2) * max(0, min(batt, 100)) / 100, y + 19,
                           fill=bcol, outline="")
        c.create_text(x + w / 2, y + 10, fill=FG, font=(SANS, 10, "bold"), text=f"{batt} %")

    # ---------- basic view ----------

    def draw_basic(self, v):
        c = self.c
        linked = self.tel.linked(v)
        cx, cy, r = 190, 210, self.HZ_R
        self.draw_horizon(cx, cy, r, v, linked)
        if linked:
            c.create_text(cx, cy + r + 22, fill=DIM, font=(MONO, 11),
                          text=f"roll {v['roll']:+4.0f}°   pitch {v['pitch']:+4.0f}°")

        x0 = 400
        self.draw_status(x0, 34, v, linked)
        c.create_text(760, 34, anchor="e", fill=DIM, font=(SANS, 9), text="Tab: advanced view")
        if not linked:
            return

        c.create_text(x0, 80, anchor="w", fill=DIM, font=(SANS, 10), text="BATTERY")
        self.draw_battery(x0, 92, 300, v["battery"])

        rows = [
            ("FLIGHT", enum_name(v["flight"])),
            ("MOVEMENT", enum_name(v["movement"])),
            ("SYSTEM", enum_name(v["system"])),
            ("HEADING", f"{v['yaw']:+5.0f}°"),
            ("HEIGHT (ToF)", fmt_range(v["bottom_cm"])),
            ("FRONT RANGE", fmt_range(v["front_cm"])),
            ("POSITION", f"x {v['x']:+.2f}  y {v['y']:+.2f}  z {v['z']:+.2f} m"),
            ("SPEED LEVEL", enum_name(v["speed"])),
            ("HEADLESS", enum_name(v["headless"])),
        ]
        for i, (k, val) in enumerate(rows):
            y = 140 + i * 28
            c.create_text(x0, y, anchor="w", fill=DIM, font=(SANS, 10), text=k)
            c.create_text(x0 + 130, y, anchor="w", fill=FG, font=(MONO, 12), text=val)

        if v["front_cm"] < 50:
            c.create_text(cx, 30, fill=BAD, font=(SANS, 14, "bold"),
                          text=f"OBSTACLE {v['front_cm']:.0f} cm")

    # ---------- advanced view ----------

    def draw_advanced(self, v, history):
        c = self.c
        W, H = c.winfo_width(), c.winfo_height()
        linked = self.tel.linked(v)
        self.draw_status(0, 14, v, linked)
        c.create_text(W, 14, anchor="e", fill=DIM, font=(SANS, 9),
                      text=f"Tab: basic view   ·   graphs: last {HISTORY_S} s")

        panel_w = 340
        top = 40
        self.draw_panel(0, top, panel_w, H - top, v, linked)

        # chart grid: 11 time charts + 1 top-down position trail
        gx, gw, gh = panel_w + 12, W - panel_w - 12, H - top
        cols, rows = 4, 3
        cw, ch = gw / cols, gh / rows
        now = self.tel.now()
        for i, (title, unit, series, ylim) in enumerate(CHARTS):
            x = gx + (i % cols) * cw
            y = top + (i // cols) * ch
            data = [(label, SERIES[k], history[key], v.get(key)) for k, (label, key) in enumerate(series)]
            self.draw_chart(x, y, cw - 8, ch - 8, title, unit, data, ylim, now)
        i = len(CHARTS)
        self.draw_trail(gx + (i % cols) * cw, top + (i // cols) * ch, cw - 8, ch - 8,
                        history["x"], history["y"], v.get("yaw", 0), linked)

    def draw_panel(self, x, y, w, h, v, linked):
        c = self.c
        c.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline="")
        cx, cy, r = x + w / 2, y + 74, 64
        self.draw_horizon(cx, cy, r, v, linked)
        if not linked:
            return

        yy = cy + r + 14
        self.draw_battery(x + 12, yy, w - 24, v["battery"])
        yy += 32

        def section(title):
            nonlocal yy
            yy += 6
            c.create_text(x + 12, yy, anchor="w", fill=ACCENT, font=(SANS, 9, "bold"), text=title)
            yy += 17

        def row(label, value, color=FG):
            nonlocal yy
            c.create_text(x + 12, yy, anchor="w", fill=DIM, font=(SANS, 9), text=label)
            c.create_text(x + 110, yy, anchor="w", fill=color, font=(MONO, 9), text=str(value))
            yy += 16

        section("STATE")
        row("flight", enum_name(v["flight"]))
        row("movement", enum_name(v["movement"]))
        row("system", enum_name(v["system"]))
        row("control mode", enum_name(v["control_mode"]))
        row("headless", enum_name(v["headless"]))
        row("speed level", enum_name(v["speed"]))
        row("orientation", enum_name(v["orientation"]))

        section("SENSORS")
        row("front / bottom", f"{fmt_range(v['front_cm']).strip()} / {fmt_range(v['bottom_cm']).strip()}")
        row("temperature", f"{fmt_num(v['temp_c'])} °C")
        row("elevation", f"{fmt_num(v['elevation_m'])} m")
        row("raw accel", " ".join(fmt_num(n, 0) for n in v["raw_accel"]))
        row("raw gyro", " ".join(fmt_num(n, 0) for n in v["raw_gyro"]))

        section("COLOR SENSORS")
        for side in ("front", "back"):
            c.create_rectangle(x + w - 26, yy - 6, x + w - 12, yy + 6, outline=DIM,
                               fill=rgb_hex(v[f"rgb_{side}"]))
            row(side, f"{v[f'color_{side}']}  hsvl {' '.join(fmt_num(n, 0) for n in v[f'hsvl_{side}'])}")
        row("card", enum_name(v["card"]))

        section("CONTROLLER")
        row("left stick", f"x {v['joy_left'][0]:+4}  y {v['joy_left'][1]:+4}")
        row("right stick", f"x {v['joy_right'][0]:+4}  y {v['joy_right'][1]:+4}")
        row("buttons", " ".join(map(enum_name, v["buttons"])))

        section("TRIM")
        row("r / p / y / t", " ".join(map(str, v["trim"])))

        section("FLAGS")
        flags = v["sensor_flags"] + v["state_flags"]
        if not flags:
            row("", "none", OK)
        for name in flags:
            row("", name, OK if name.startswith("RF_") else BAD)

        section("LIFETIME")
        row("flight time", v["flight_time"])
        row("takeoff / land", f"{v['takeoffs']} / {v['landings']}")
        row("accidents", v["accidents"])

        section("FIRMWARE")
        row("drone", f"{enum_name(v['drone_model'])} {v['drone_fw']}")
        row("controller", f"{enum_name(v['controller_model'])} {v['controller_fw']}")

    def draw_chart(self, x, y, w, h, title, unit, data, ylim, now):
        c = self.c
        c.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline="")
        c.create_text(x + 10, y + 12, anchor="w", fill=FG, font=(SANS, 10, "bold"),
                      text=f"{title} ({unit})" if unit else title)
        # legend with latest value, on its own line under the title
        lx = x + 10
        for label, color, _, latest in data:
            t = f"{label} {fmt_num(latest)}" if latest is not None else label
            item = c.create_text(lx, y + 30, anchor="w", fill=color, font=(MONO, 9), text=t)
            lx = c.bbox(item)[2] + 12

        px0, px1 = x + 44, x + w - 10
        py0, py1 = y + 46, y + h - 18
        values = [val for _, _, pts, _ in data for _, val in pts]
        if not values:
            c.create_text((px0 + px1) / 2, (py0 + py1) / 2, fill=DIM, font=(SANS, 9), text="no data")
            return
        if ylim:
            lo, hi = ylim
        else:
            lo, hi = min(values), max(values)
            if hi - lo < 1:
                mid = (hi + lo) / 2
                lo, hi = mid - 0.5, mid + 0.5
            pad = (hi - lo) * 0.1
            lo, hi = lo - pad, hi + pad

        def sx(t):
            return px1 - (now - t) / HISTORY_S * (px1 - px0)

        def sy(val):
            val = max(lo, min(hi, val))
            return py1 - (val - lo) / (hi - lo) * (py1 - py0)

        for k in range(3):
            gv = lo + (hi - lo) * k / 2
            gy = sy(gv)
            c.create_line(px0, gy, px1, gy, fill=GRID)
            c.create_text(px0 - 6, gy, anchor="e", fill=DIM, font=(MONO, 8), text=fmt_num(gv, 0 if hi - lo > 10 else 1))
        c.create_text(px0, py1 + 10, anchor="w", fill=DIM, font=(MONO, 8), text=f"-{HISTORY_S}s")
        c.create_text(px1, py1 + 10, anchor="e", fill=DIM, font=(MONO, 8), text="now")

        for _, color, pts, _ in data:
            # split the line where an angle wraps around (+180 -> -180)
            segments, seg, prev = [], [], None
            for t, val in pts:
                if unit == "°" and prev is not None and abs(val - prev) > 180:
                    segments.append(seg)
                    seg = []
                seg += [sx(t), sy(val)]
                prev = val
            segments.append(seg)
            for seg in segments:
                if len(seg) >= 4:
                    c.create_line(*seg, fill=color, width=2)

    def draw_trail(self, x, y, w, h, xs, ys, yaw, linked):
        """Top-down view: x forward (up on screen), y left."""
        c = self.c
        c.create_rectangle(x, y, x + w, y + h, fill=PANEL, outline="")
        c.create_text(x + 10, y + 12, anchor="w", fill=FG, font=(SANS, 10, "bold"), text="Path (top view, m)")
        if not xs:
            c.create_text(x + w / 2, y + h / 2, fill=DIM, font=(SANS, 9), text="no data")
            return
        pts = [(px, py) for (_, px), (_, py) in zip(xs, ys)]
        span = max(0.5, max(abs(n) for p in pts for n in p) * 1.2)
        cx, cy = x + w / 2, y + 16 + (h - 16) / 2
        scale = (min(w, h - 16) / 2 - 12) / span

        def sp(px, py):
            return cx - py * scale, cy - px * scale

        c.create_line(x + 10, cy, x + w - 10, cy, fill=GRID)
        c.create_line(cx, y + 26, cx, y + h - 6, fill=GRID)
        c.create_text(x + w - 10, y + h - 8, anchor="e", fill=DIM, font=(MONO, 8), text=f"±{span:.1f} m")
        if len(pts) >= 2:
            c.create_line(*[n for p in pts for n in sp(*p)], fill=SERIES[0], width=2)
        dx, dy = sp(*pts[-1])
        if linked:
            a = math.radians(yaw)
            c.create_line(dx, dy, dx - math.sin(a) * 18, dy - math.cos(a) * 18,
                          fill=ACCENT, width=2, arrow="last")
        c.create_oval(dx - 5, dy - 5, dx + 5, dy + 5, fill=ACCENT, outline="")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = args[0] if args else None
    drone = Drone()
    drone.pair(port)

    tel = Telemetry(drone)
    tel.start()

    root = tk.Tk()
    Hud(root, tel, advanced="--advanced" in sys.argv)
    try:
        root.mainloop()
    finally:
        tel.stop()
        drone.close()


if __name__ == "__main__":
    main()
