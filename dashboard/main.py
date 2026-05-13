import socket
import numpy as np
import threading
import time
import struct
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.gridspec as gridspec
from collections import deque
import tkinter as tk
import math

# ============================================================
#  ███████╗███████╗████████╗████████╗██╗███╗   ██╗ ██████╗ ███████╗
#  ██╔════╝██╔════╝╚══██╔══╝╚══██╔══╝██║████╗  ██║██╔════╝ ██╔════╝
#  ███████╗█████╗     ██║      ██║   ██║██╔██╗ ██║██║  ███╗███████╗
#  ╚════██║██╔══╝     ██║      ██║   ██║██║╚██╗██║██║   ██║╚════██║
#  ███████║███████╗   ██║      ██║   ██║██║ ╚████║╚██████╔╝███████║
#  ╚══════╝╚══════╝   ╚═╝      ╚═╝   ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚══════╝
# ============================================================
# All tuneable parameters are here.
# ============================================================

# ─────────────────────────────────────────────────────────────
# 1. NETWORK
# ─────────────────────────────────────────────────────────────

UDP_IP      = "0.0.0.0"
UDP_PORT_A  = 8001          # Node A (LEFT)
UDP_PORT_B  = 8000          # Node B (RIGHT)
STARTUP_PACKET_WAIT  = 5
STARTUP_TIMEOUT_SEC  = 30

# ─────────────────────────────────────────────────────────────
# 2. BUFFER / HISTORY
# ─────────────────────────────────────────────────────────────

HISTORY_SIZE    = 500
MAX_SUBCARRIERS = 64
TIME_WINDOW     = 40
CONNECTION_ALIVE_SEC = 2.0

# ─────────────────────────────────────────────────────────────
# 3. RECEIVER INTERNALS
# ─────────────────────────────────────────────────────────────

UDP_SOCKET_TIMEOUT       = 0.02
UDP_BATCH_SIZE           = 50
NULL_THRESHOLD_FRACTION  = 0.98

# ─────────────────────────────────────────────────────────────
# 4. DIGIT FEATURE EXTRACTOR
# ─────────────────────────────────────────────────────────────

DIGIT_EMA_ALPHA          = 0.05
DIGIT_NORM_WINDOW        = 200
DIGIT_TRIM_PERCENTILE    = 95
DIGIT_NORM_LO_PERCENTILE = 2
DIGIT_NORM_HI_PERCENTILE = 98
DIGIT_HISTORY            = HISTORY_SIZE
HALF_BAND_MIN_VALID_UPPER = 8

# ─────────────────────────────────────────────────────────────
# 5. PRESENCE DETECTION
# ─────────────────────────────────────────────────────────────

PRESENCE_THRESHOLD      = 4.0
# Hysteresis: once confirmed LOW, digit must rise above this to go back to high.
# Prevents flickering around the threshold edge. Set higher than PRESENCE_THRESHOLD.
PRESENCE_HYSTERESIS_HI  = 5.2

CONFIRMATION_STREAK = 15
STREAK_DECAY_ON_NAN = 1
MOVE_HOLD_FRAMES    = 30   # frames to keep walking arrow after both nodes go clear

# Crossing state: stickman scale factor (> 1 = bigger = "closer / focal point")
CROSSING_SCALE      = 1.55   # how much bigger the stickman gets when crossing

# ─────────────────────────────────────────────────────────────
# 6. MOVEMENT DETECTION  (NEW — trajectory tracking)
# ─────────────────────────────────────────────────────────────

# How long (seconds) a confirmed detection is "remembered" for
# direction inference after it clears.
DIRECTION_MEMORY_SEC = 3.0

# Minimum digit delta between the two nodes to infer which way
# the person is travelling when both are above threshold.
# e.g.  A=3.1, B=6.8  → person closer to A, moving toward B
DIRECTION_DIGIT_DELTA = 0.8

# ─────────────────────────────────────────────────────────────
# 7. STICKMAN ANIMATION
# ─────────────────────────────────────────────────────────────

STICKMAN_FPS            = 20
STICKMAN_LERP_WALK      = 0.055   # smooth glide while walking
STICKMAN_LERP_IDLE      = 0.10
STICKMAN_WALK_PHASE_STEP = 0.20
STICKMAN_POSE_DAMP_STEP  = 0.10
STICKMAN_SWING_AMPLITUDE = 24
STICKMAN_ARM_SWING_FACTOR = 0.60
STICKMAN_LEG_SWING_FACTOR = 0.60
STICKMAN_ARROW_LENGTH    = 42
STICKMAN_STAND_OFFSET    = 70

# ─────────────────────────────────────────────────────────────
# 8. HEATMAP DISPLAY
# ─────────────────────────────────────────────────────────────

HEATMAP_CMAP                = 'turbo'
HEATMAP_VMIN                = 0
HEATMAP_VMAX                = 50
HEATMAP_AUTOSCALE_INTERVAL  = 30
HEATMAP_AUTOSCALE_PERCENTILE = 98
HEATMAP_NULL_COLOR          = '#111111'
HEATMAP_INTERPOLATION       = 'bilinear'
FIGURE_SIZE                 = (16, 12)
ANIMATION_INTERVAL_MS       = 50

# ─────────────────────────────────────────────────────────────
# 9. RSSI PANEL
# ─────────────────────────────────────────────────────────────

RSSI_YLIM_MIN            = -95
RSSI_YLIM_MAX            = -20
RSSI_AUTOSCALE_PAD       = 4
RSSI_AUTOSCALE_PAD_FRACTION = 0.20

# ─────────────────────────────────────────────────────────────
# 10. STICKMAN WINDOW GEOMETRY
# ─────────────────────────────────────────────────────────────

STICK_WIN_W   = 760
STICK_WIN_H   = 360
STICK_FLOOR_Y = 272

STICK_HEAD_R   = 24
STICK_BODY_LEN = 66
STICK_LEG_LEN  = 58
STICK_ARM_LEN  = 40

STICK_NODE_A_X = 68
STICK_NODE_B_X = STICK_WIN_W - 68

# ─────────────────────────────────────────────────────────────
# 11. STICKMAN STATE COLOURS
# ─────────────────────────────────────────────────────────────

COLOR_IDLE      = '#445566'
COLOR_AT_LEFT   = '#00ffcc'
COLOR_AT_RIGHT  = '#ff9900'
COLOR_MOVING    = '#e8e8ff'
COLOR_CROSSING  = '#ff4444'

# ─────────────────────────────────────────────────────────────
# 12. STREAK BAR COLOURS
# ─────────────────────────────────────────────────────────────

COLOR_STREAK_A_FILL    = '#00ffcc'
COLOR_STREAK_A_FULL    = '#00ff88'
COLOR_STREAK_A_BG      = '#112211'
COLOR_STREAK_A_OUTLINE = '#224433'

COLOR_STREAK_B_FILL    = '#ff9900'
COLOR_STREAK_B_FULL    = '#ffcc44'
COLOR_STREAK_B_BG      = '#221100'
COLOR_STREAK_B_OUTLINE = '#332200'

# ============================================================
# END OF SETTINGS
# ============================================================


# ==========================================
# SHARED SUBCARRIER MASK
# ==========================================
class SubcarrierMask:
    def __init__(self, n=MAX_SUBCARRIERS):
        self._lock = threading.Lock()
        self._mask = [True] * n
        self.n = n

    def get(self, idx):
        with self._lock: return self._mask[idx]

    def set(self, idx, val):
        with self._lock: self._mask[idx] = val

    def get_all(self):
        with self._lock: return list(self._mask)

    def set_all(self, val):
        with self._lock: self._mask = [val] * self.n


# ==========================================
# TKINTER SELECTOR WINDOW
# ==========================================
def launch_selector_window(mask: SubcarrierMask):
    root = tk.Tk()
    root.title("Subcarrier Selector  —  Shared (Node A & B)")
    root.configure(bg='#0d0d0d')
    root.resizable(False, False)

    tk.Label(root, text="Subcarrier Selector",
             bg='#0d0d0d', fg='#00ffcc',
             font=('Courier', 13, 'bold')).grid(row=0, column=0, columnspan=8, pady=(10, 2))

    tk.Label(root, text="Applies to both Node A and Node B",
             bg='#0d0d0d', fg='#556677',
             font=('Courier', 8)).grid(row=1, column=0, columnspan=8, pady=(0, 8))

    COLS  = 8
    vars_ = []

    def make_toggle(idx, var):
        def _toggle(): mask.set(idx, bool(var.get()))
        return _toggle

    for sc in range(MAX_SUBCARRIERS):
        row = 2 + (sc // COLS)
        col = sc % COLS
        var = tk.IntVar(value=1)
        vars_.append(var)
        cb = tk.Checkbutton(
            root, text=f"{sc:02d}", variable=var,
            command=make_toggle(sc, var),
            bg='#0d0d0d', fg='#00ffcc', selectcolor='#003322',
            activebackground='#0d0d0d', activeforeground='#00ffcc',
            font=('Courier', 8), width=4, anchor='w', bd=0, highlightthickness=0)
        cb.grid(row=row, column=col, padx=3, pady=2, sticky='w')

    btn_frame = tk.Frame(root, bg='#0d0d0d')
    btn_frame.grid(row=2 + MAX_SUBCARRIERS // COLS, column=0, columnspan=8, pady=(10, 6))

    def all_on():
        mask.set_all(True)
        for v in vars_: v.set(1)

    def all_off():
        mask.set_all(False)
        for v in vars_: v.set(0)

    BTN = dict(font=('Courier', 9, 'bold'), relief='flat', padx=12, pady=4, cursor='hand2', bd=0)
    tk.Button(btn_frame, text="ALL ON",  bg='#003322', fg='#00ffcc',
              activebackground='#005533', command=all_on,  **BTN).pack(side='left', padx=8)
    tk.Button(btn_frame, text="ALL OFF", bg='#220000', fg='#ff4444',
              activebackground='#440000', command=all_off, **BTN).pack(side='left', padx=8)

    status_var = tk.StringVar(value=f"{MAX_SUBCARRIERS} / {MAX_SUBCARRIERS} active")
    tk.Label(root, textvariable=status_var, bg='#0d0d0d', fg='#556677',
             font=('Courier', 8)).grid(row=3 + MAX_SUBCARRIERS // COLS, column=0,
                                       columnspan=8, pady=(0, 10))

    def refresh_status():
        status_var.set(f"{sum(mask.get_all())} / {MAX_SUBCARRIERS} active")
        root.after(300, refresh_status)

    refresh_status()
    root.mainloop()


# ==========================================
# ESP32 SUBCARRIER LAYOUT HELPERS
# ==========================================
def expand_to_64(amp: np.ndarray, count: int) -> np.ndarray:
    frame = np.zeros(MAX_SUBCARRIERS, dtype=np.float32)
    if count == MAX_SUBCARRIERS:
        frame[:] = amp
    elif count == 56:
        valid = list(range(3, 32)) + list(range(33, 61))
        valid = valid[:count]
        for i, s in enumerate(valid): frame[s] = amp[i]
    elif count == 52:
        valid = (list(range(4, 7))   + list(range(8, 21))  +
                 list(range(22, 32)) + list(range(33, 43)) +
                 list(range(44, 57)) + list(range(58, 61)))
        valid = valid[:count]
        for i, s in enumerate(valid): frame[s] = amp[i]
    elif count == 32:
        frame[:32] = amp[:32]
    else:
        n = min(count, MAX_SUBCARRIERS)
        frame[:n] = amp[:n]
    return frame


# ==========================================
# BINARY CSI RECEIVER
# ==========================================
class BinaryCSIReceiver:
    def __init__(self, port, label="Node"):
        self.port  = port
        self.label = label
        self.sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((UDP_IP, port))
        self.sock.settimeout(UDP_SOCKET_TIMEOUT)

        self.running = False
        self.csi_buffer  = deque(maxlen=HISTORY_SIZE)
        self.rssi_buffer = deque(maxlen=HISTORY_SIZE)
        self.time_buffer = deque(maxlen=HISTORY_SIZE)
        self.lock = threading.Lock()

        self.packet_count     = 0
        self._last_count      = 0
        self._last_time       = time.time()
        self.pps              = 0
        self.last_packet_time = time.time()
        self._count_log: dict = {}
        print(f"📡 [{label}] Receiver initialized on port {port}")

    def start(self):
        self.running = True
        threading.Thread(target=self._worker, daemon=True).start()
        print(f"✅ [{self.label}] Receiver thread started...")

    def stop(self):
        self.running = False
        try: self.sock.close()
        except Exception: pass

    def _worker(self):
        while self.running:
            try:
                packets = []
                for _ in range(UDP_BATCH_SIZE):
                    try:
                        data, _ = self.sock.recvfrom(4096)
                        packets.append(data)
                    except socket.timeout: break
                    except BlockingIOError: break

                if not packets:
                    time.sleep(0.001)
                    continue

                with self.lock:
                    for pkt in packets: self._process(pkt)

                self.packet_count += len(packets)
                self.last_packet_time = time.time()

                now = time.time()
                if now - self._last_time >= 1.0:
                    self.pps         = self.packet_count - self._last_count
                    self._last_count = self.packet_count
                    self._last_time  = now

            except Exception as e:
                if self.running: print(f"⚠️  [{self.label}] Worker error: {e}")
                time.sleep(0.01)

    def _process(self, data: bytes):
        try:
            if len(data) < 8: return
            timestamp, rssi_u, count, pad1, pad2 = struct.unpack('<IBBbb', data[:8])
            rssi = rssi_u - 256 if rssi_u > 127 else -rssi_u
            self._count_log[count] = self._count_log.get(count, 0) + 1
            if self.packet_count < 5:
                print(f"🔍 [{self.label}] count={count}  rssi={rssi} dBm  pkt_len={len(data)}")
            if count < 1 or count > MAX_SUBCARRIERS: return
            expected = 8 + count * 4
            if len(data) < expected: return
            raw  = struct.unpack(f'<{count * 2}h', data[8:expected])
            real = np.array(raw[0::2], dtype=np.float32)
            imag = np.array(raw[1::2], dtype=np.float32)
            amp  = np.sqrt(real**2 + imag**2)
            frame = expand_to_64(amp, count)
            self.csi_buffer.append(frame)
            self.rssi_buffer.append(rssi)
            self.time_buffer.append(time.time())
        except Exception: pass

    def get_data(self):
        with self.lock:
            if not self.time_buffer:
                return (np.full((MAX_SUBCARRIERS, HISTORY_SIZE), np.nan),
                        np.array([]), np.array([]), self.pps, False)
            now    = time.time()
            times  = np.array(self.time_buffer)
            in_win = times >= (now - TIME_WINDOW)
            if not np.any(in_win):
                return (np.full((MAX_SUBCARRIERS, HISTORY_SIZE), np.nan),
                        np.array([]), np.array([]), self.pps, False)
            idx_list  = [i for i, v in enumerate(in_win) if v]
            csi_list  = list(self.csi_buffer)
            rssi_list = list(self.rssi_buffer)
            csi  = np.array([csi_list[i]  for i in idx_list], dtype=np.float32).T
            rssi = np.array([rssi_list[i] for i in idx_list], dtype=np.float32)
            t_w  = times[in_win]
            alive = (now - self.last_packet_time) < CONNECTION_ALIVE_SEC
            if csi.shape[1] > 10:
                zero_frac = np.mean(csi == 0, axis=1)
                csi[zero_frac > NULL_THRESHOLD_FRACTION, :] = np.nan
            return csi, rssi, t_w, self.pps, alive


# ==========================================
# SINGLE-DIGIT FEATURE EXTRACTOR
# ==========================================
class DigitExtractor:
    def __init__(self):
        self._ema  = None
        self._norm = deque(maxlen=DIGIT_NORM_WINDOW)
        self.digit_history = deque([np.nan] * DIGIT_HISTORY, maxlen=DIGIT_HISTORY)

    def push(self, csi_col: np.ndarray, active_mask: list) -> float:
        col = csi_col.copy()
        for i, active in enumerate(active_mask):
            if not active: col[i] = np.nan

        if np.sum(~np.isnan(col[32:])) < HALF_BAND_MIN_VALID_UPPER:
            col[32:] = np.nan

        valid = col[~np.isnan(col)]
        if valid.size == 0:
            self.digit_history.append(np.nan)
            return np.nan

        cutoff  = np.percentile(valid, DIGIT_TRIM_PERCENTILE)
        trimmed = valid[valid <= cutoff]
        raw_val = float(np.median(trimmed)) if trimmed.size > 0 else float(np.median(valid))

        if self._ema is None:
            self._ema = raw_val
        else:
            self._ema = DIGIT_EMA_ALPHA * raw_val + (1 - DIGIT_EMA_ALPHA) * self._ema

        self._norm.append(self._ema)
        norm_arr = np.array(self._norm)
        lo = np.percentile(norm_arr, DIGIT_NORM_LO_PERCENTILE)
        hi = np.percentile(norm_arr, DIGIT_NORM_HI_PERCENTILE)

        if hi - lo < 1e-3:
            digit = 4.5
        else:
            digit = np.clip((self._ema - lo) / (hi - lo) * 9, 0, 9)

        self.digit_history.append(digit)
        return digit

    def current_digit(self) -> float:
        arr   = np.array(self.digit_history)
        valid = arr[~np.isnan(arr)]
        return float(valid[-1]) if valid.size > 0 else np.nan


# ==========================================
# STREAK-BASED PRESENCE DETECTOR  (with hysteresis)
# ==========================================
# Uses two thresholds to prevent flickering:
#   confirm LOW  (present): digit drops below PRESENCE_THRESHOLD
#   confirm HIGH (gone):    digit rises above PRESENCE_HYSTERESIS_HI
class PresenceDetector:
    def __init__(self):
        self.streak        = 0
        self.confirmed_low = False
        self._trying_low   = False   # which direction current streak is building toward

    def update(self, digit: float) -> bool:
        if math.isnan(digit):
            self.streak = max(0, self.streak - STREAK_DECAY_ON_NAN)
            return self.confirmed_low

        # Hysteresis: different exit threshold once confirmed
        if self.confirmed_low:
            instant = digit < PRESENCE_HYSTERESIS_HI   # must rise past HI to clear
        else:
            instant = digit < PRESENCE_THRESHOLD        # must drop past LO to trigger

        if instant == self._trying_low:
            self.streak += 1
        else:
            self.streak      = 1
            self._trying_low = instant

        if self.streak >= CONFIRMATION_STREAK:
            self.confirmed_low = instant

        return self.confirmed_low


# ==========================================
# DIRECTION TRACKER  (NEW)
# ==========================================
# Maintains a short event log of node confirmations and uses it
# to infer travel direction much more reliably than the old
# _prev_conf heuristic.
#
# Core idea:
#   • Each time conf_a or conf_b *rises* (False→True), we record
#     which node fired and the current timestamp.
#   • Direction = "A→B" if the most recent RISE was on B and the
#     previous RISE (within DIRECTION_MEMORY_SEC) was on A,
#     and vice-versa.
#   • If both nodes are simultaneously confirmed we check which
#     digit is lower — the lower one is where the person
#     currently is, and we infer they're heading toward the
#     higher one (about to leave that zone).
#   • The direction is "locked" (persisted) for DIRECTION_MEMORY_SEC
#     after the last relevant event so the arrow stays visible
#     while the person is crossing open space.
# ==========================================
class DirectionTracker:
    NONE   = 0
    A_TO_B = 1   # moving right
    B_TO_A = 2   # moving left

    def __init__(self):
        # Ring buffer of (timestamp, node_label, event_type) where
        # event_type is 'rise' (False→True) or 'fall' (True→False)
        self._events: deque = deque(maxlen=30)
        self._prev_conf_a   = False
        self._prev_conf_b   = False
        self._locked_dir    = self.NONE
        self._lock_time     = 0.0

    def update(self, conf_a: bool, conf_b: bool,
               digit_a: float, digit_b: float) -> int:
        now = time.time()

        rose_a = conf_a and not self._prev_conf_a
        fell_a = not conf_a and self._prev_conf_a
        rose_b = conf_b and not self._prev_conf_b
        fell_b = not conf_b and self._prev_conf_b

        if rose_a: self._events.append((now, 'A', 'rise'))
        if fell_a: self._events.append((now, 'A', 'fall'))
        if rose_b: self._events.append((now, 'B', 'rise'))
        if fell_b: self._events.append((now, 'B', 'fall'))

        self._prev_conf_a = conf_a
        self._prev_conf_b = conf_b

        # Expire old events
        cutoff = now - DIRECTION_MEMORY_SEC
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

        direction = self.NONE
        events_list = list(self._events)

        # ── Strategy 1: classic A-rise then B-rise = A→B, or B-rise then A-rise = B→A
        rises = [(t, node) for t, node, etype in events_list if etype == 'rise']
        if len(rises) >= 2:
            last, prev = rises[-1], rises[-2]
            if prev[1] == 'A' and last[1] == 'B':
                direction = self.A_TO_B
            elif prev[1] == 'B' and last[1] == 'A':
                direction = self.B_TO_A

        # ── Strategy 2: A-fall then B-rise = A→B, B-fall then A-rise = B→A
        #    (person leaves A zone, enters B zone — very clean signal)
        if direction == self.NONE and len(events_list) >= 2:
            for i in range(len(events_list) - 1, 0, -1):
                t2, n2, e2 = events_list[i]
                for j in range(i - 1, -1, -1):
                    t1, n1, e1 = events_list[j]
                    if e1 == 'fall' and e2 == 'rise' and n1 != n2:
                        if n1 == 'A' and n2 == 'B':
                            direction = self.A_TO_B
                        elif n1 == 'B' and n2 == 'A':
                            direction = self.B_TO_A
                        break
                if direction != self.NONE:
                    break

        # ── Strategy 3: both confirmed simultaneously → digit gradient
        if direction == self.NONE and conf_a and conf_b:
            da = digit_a if not math.isnan(digit_a) else 5.0
            db = digit_b if not math.isnan(digit_b) else 5.0
            if abs(da - db) >= DIRECTION_DIGIT_DELTA:
                # Lower digit = person physically closer to that node
                # They're "at" the lower node, heading toward the higher
                direction = self.A_TO_B if da < db else self.B_TO_A

        # ── Strategy 4: single node active, infer from digit asymmetry
        #    Even when only one node is triggered, the OTHER node's digit
        #    dropping slightly can reveal which way the person is facing.
        if direction == self.NONE:
            da = digit_a if not math.isnan(digit_a) else 9.0
            db = digit_b if not math.isnan(digit_b) else 9.0
            if conf_a and not conf_b:
                # Person confirmed at A. If B is also slightly disturbed,
                # they may be moving toward B.
                if db < (PRESENCE_THRESHOLD + 2.0) and da < db:
                    direction = self.A_TO_B
            elif conf_b and not conf_a:
                if da < (PRESENCE_THRESHOLD + 2.0) and db < da:
                    direction = self.B_TO_A

        # Lock direction so arrow persists while crossing open space
        if direction != self.NONE:
            self._locked_dir = direction
            self._lock_time  = now
        elif now - self._lock_time > DIRECTION_MEMORY_SEC:
            self._locked_dir = self.NONE

        active_dir = (direction if direction != self.NONE
                      else (self._locked_dir
                            if now - self._lock_time <= DIRECTION_MEMORY_SEC
                            else self.NONE))
        return active_dir


# ==========================================
# VISUAL STICKMAN  (improved drawing)
# ==========================================
def _draw_rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on a Tk canvas."""
    canvas.create_arc(x1,     y1,     x1+2*r, y1+2*r, start=90,  extent=90,  style='arc', **kw)
    canvas.create_arc(x2-2*r, y1,     x2,     y1+2*r, start=0,   extent=90,  style='arc', **kw)
    canvas.create_arc(x1,     y2-2*r, x1+2*r, y2,     start=180, extent=90,  style='arc', **kw)
    canvas.create_arc(x2-2*r, y2-2*r, x2,     y2,     start=270, extent=90,  style='arc', **kw)
    canvas.create_line(x1+r, y1, x2-r, y1, **kw)
    canvas.create_line(x1+r, y2, x2-r, y2, **kw)
    canvas.create_line(x1, y1+r, x1, y2-r, **kw)
    canvas.create_line(x2, y1+r, x2, y2-r, **kw)


def _draw_filled_rounded_rect(canvas, x1, y1, x2, y2, r, fill, outline, width=1):
    """Draw a filled rounded rectangle."""
    canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline='')
    canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline='')
    canvas.create_oval(x1, y1, x1+2*r, y1+2*r, fill=fill, outline='')
    canvas.create_oval(x2-2*r, y1, x2, y1+2*r, fill=fill, outline='')
    canvas.create_oval(x1, y2-2*r, x1+2*r, y2, fill=fill, outline='')
    canvas.create_oval(x2-2*r, y2-2*r, x2, y2, fill=fill, outline='')
    if outline:
        _draw_rounded_rect(canvas, x1, y1, x2, y2, r, fill=outline, width=width)


class StickmanWindow:

    def __init__(self, de_a: DigitExtractor, de_b: DigitExtractor):
        self.de_a = de_a
        self.de_b = de_b

        self.det_a = PresenceDetector()
        self.det_b = PresenceDetector()
        self.dir_tracker = DirectionTracker()

        self._state       = 'idle'
        self._direction   = DirectionTracker.NONE
        self._x           = STICK_WIN_W / 2
        self._target_x    = STICK_WIN_W / 2
        self._walk_phase  = 0.0
        self._walk_speed  = 0    # -1, 0, +1
        self._hold_count  = 0
        self._running     = True

        # Glow pulse for idle state
        self._pulse_t     = 0.0

        # Visual scale: 1.0 = normal, > 1.0 = person closer (crossing state)
        self._scale       = 1.0
        self._target_scale = 1.0

    def launch(self):
        self._root = tk.Tk()
        self._root.title("CSI Motion Tracker")
        self._root.configure(bg='#080c10')
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Title bar
        title_frame = tk.Frame(self._root, bg='#080c10')
        title_frame.pack(fill='x', padx=12, pady=(10, 0))
        tk.Label(title_frame, text="◈ CSI MOTION TRACKER",
                 bg='#080c10', fg='#00ffcc',
                 font=('Courier', 11, 'bold')).pack(side='left')
        tk.Label(title_frame, text="DUAL NODE",
                 bg='#080c10', fg='#334455',
                 font=('Courier', 9)).pack(side='right')

        # Main canvas
        self._canvas = tk.Canvas(
            self._root, width=STICK_WIN_W, height=STICK_WIN_H,
            bg='#080c10', highlightthickness=0)
        self._canvas.pack(padx=12, pady=(6, 4))

        # Streak bars
        self._streak_canvas = tk.Canvas(
            self._root, width=STICK_WIN_W, height=30,
            bg='#080c10', highlightthickness=0)
        self._streak_canvas.pack(padx=12)

        # Status + digit row
        info_frame = tk.Frame(self._root, bg='#080c10')
        info_frame.pack(pady=(6, 2))

        self._status_var = tk.StringVar(value="Waiting for data…")
        tk.Label(info_frame, textvariable=self._status_var,
                 bg='#080c10', fg='#aabbcc',
                 font=('Courier', 10)).pack(side='top')

        df = tk.Frame(info_frame, bg='#080c10')
        df.pack(side='top', pady=(3, 0))
        self._da_var = tk.StringVar(value="A: –")
        self._db_var = tk.StringVar(value="B: –")
        self._dir_var = tk.StringVar(value="→ –")

        tk.Label(df, textvariable=self._da_var, bg='#080c10',
                 fg=COLOR_AT_LEFT,  font=('Courier', 12, 'bold')).pack(side='left', padx=16)
        tk.Label(df, textvariable=self._dir_var, bg='#080c10',
                 fg='#778899', font=('Courier', 11)).pack(side='left', padx=8)
        tk.Label(df, textvariable=self._db_var, bg='#080c10',
                 fg=COLOR_AT_RIGHT, font=('Courier', 12, 'bold')).pack(side='left', padx=16)

        tk.Frame(self._root, bg='#080c10', height=8).pack()

        self._draw_scene()
        self._schedule_update()
        self._root.mainloop()

    def _on_close(self):
        self._running = False
        self._root.destroy()

    def _schedule_update(self):
        if self._running:
            self._update()
            self._root.after(int(1000 / STICKMAN_FPS), self._schedule_update)

    # ------------------------------------------------------------------
    # State machine  (simplified — direction handled by DirectionTracker)
    # ------------------------------------------------------------------
    def _compute_state(self, conf_a: bool, conf_b: bool, direction: int) -> str:
        """
        State mapping:
          both confirmed            → 'crossing'
          A only + dir=A→B          → 'moving_right'   (confirmed at A, heading to B)
          B only + dir=B→A          → 'moving_left'    (confirmed at B, heading to A)
          A only + no clear dir     → 'at_left'
          B only + no clear dir     → 'at_right'
          neither + direction known → 'moving_right/left' (hold for MOVE_HOLD_FRAMES)
          neither + no direction    → 'idle'
        """
        DT = DirectionTracker

        if conf_a and conf_b:
            self._hold_count = 0
            return 'crossing'

        if conf_a and not conf_b:
            self._hold_count = 0
            if direction == DT.A_TO_B:
                return 'moving_right'
            return 'at_left'

        if conf_b and not conf_a:
            self._hold_count = 0
            if direction == DT.B_TO_A:
                return 'moving_left'
            return 'at_right'

        # Neither confirmed
        if direction != DT.NONE:
            if self._hold_count < MOVE_HOLD_FRAMES:
                self._hold_count += 1
                return 'moving_right' if direction == DT.A_TO_B else 'moving_left'
            else:
                self._hold_count = 0

        return 'idle'

    def _target_for_state(self, state: str):
        """Returns (target_x_pixels, walk_speed_sign, target_scale)"""
        if state == 'at_left':       return STICK_NODE_A_X + STICKMAN_STAND_OFFSET, 0,  1.0
        if state == 'at_right':      return STICK_NODE_B_X - STICKMAN_STAND_OFFSET, 0,  1.0
        if state == 'moving_right':  return STICK_NODE_B_X - STICKMAN_STAND_OFFSET, +1, 1.0
        if state == 'moving_left':   return STICK_NODE_A_X + STICKMAN_STAND_OFFSET, -1, 1.0
        # crossing: stay at current position (or center) but grow larger
        if state == 'crossing':      return self._x,                                 0,  CROSSING_SCALE
        return STICK_WIN_W / 2, 0, 1.0   # idle

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _state_color(self):
        return {
            'idle':         COLOR_IDLE,
            'at_left':      COLOR_AT_LEFT,
            'at_right':     COLOR_AT_RIGHT,
            'moving_right': COLOR_MOVING,
            'moving_left':  COLOR_MOVING,
            'crossing':     COLOR_CROSSING,
        }.get(self._state, COLOR_MOVING)

    def _draw_background(self):
        """Subtle grid / scanlines for a tech feel."""
        c = self._canvas
        W, H = STICK_WIN_W, STICK_WIN_H
        # Horizontal scanlines
        for y in range(0, H, 18):
            c.create_line(0, y, W, y, fill='#0e1420', width=1)
        # Vertical grid
        for x in range(0, W, 60):
            c.create_line(x, 0, x, H, fill='#0e1420', width=1)

    def _draw_floor(self):
        c = self._canvas
        y = STICK_FLOOR_Y
        W = STICK_WIN_W
        # Gradient-ish floor line via stacked lines
        c.create_line(20, y+2, W-20, y+2, fill='#0d1a24', width=2)
        c.create_line(20, y,   W-20, y,   fill='#1a3a50', width=2)
        c.create_line(20, y-1, W-20, y-1, fill='#22557a', width=1)

        # Floor reflection strip
        c.create_rectangle(20, y+1, W-20, y+6, fill='#0a1520', outline='')

        # Dashed beam connecting the two nodes
        y_beam = STICK_FLOOR_Y - 32
        dash_col = '#152535'
        for x in range(STICK_NODE_A_X + 28, STICK_NODE_B_X - 28, 16):
            c.create_line(x, y_beam, x+10, y_beam, fill=dash_col, width=1)

    @staticmethod
    def _dim_color(hex_color: str, factor: float) -> str:
        """Return a darkened version of a #rrggbb colour. factor=0→black, 1→original."""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = int(r * factor); g = int(g * factor); b = int(b * factor)
        return f'#{r:02x}{g:02x}{b:02x}'

    def _draw_node(self, x, label, color, is_active: bool):
        c  = self._canvas
        fy = STICK_FLOOR_Y

        # Glow under active node — use progressively dimmed colours (no alpha needed)
        if is_active:
            glow_levels = [(32, 0.08), (24, 0.12), (16, 0.18), (10, 0.28), (6, 0.40)]
            for radius, factor in glow_levels:
                gc = self._dim_color(color, factor)
                c.create_oval(x - radius*2, fy - 6,
                              x + radius*2, fy + radius//2,
                              fill='', outline=gc, width=1)

        # Tower body with gradient look (stacked rectangles)
        tower_colors = ['#0d1f2d', '#102535', '#132c3e']
        for i, tc in enumerate(tower_colors):
            c.create_rectangle(x - 7 + i//2, fy - 80 + i, x + 7 - i//2, fy,
                                fill=tc, outline='')
        c.create_rectangle(x - 7, fy - 80, x + 7, fy,
                            fill='', outline=color, width=1)

        # Antenna
        c.create_line(x, fy - 80, x - 20, fy - 112, fill=color, width=2)
        c.create_line(x, fy - 80, x + 20, fy - 112, fill=color, width=2)
        c.create_line(x, fy - 60, x - 14, fy - 78,  fill=color, width=1)
        c.create_line(x, fy - 60, x + 14, fy - 78,  fill=color, width=1)

        # Antenna tip dots
        c.create_oval(x - 22, fy - 116, x - 18, fy - 112, fill=color, outline='')
        c.create_oval(x + 18,  fy - 116, x + 22, fy - 112, fill=color, outline='')

        # Signal rings (animated for active)
        if is_active:
            pulse = (math.sin(self._pulse_t * 3) + 1) * 0.5
            ring_r = int(18 + pulse * 12)
            c.create_oval(x - ring_r, fy - 95 - ring_r//2,
                          x + ring_r, fy - 95 + ring_r//2,
                          fill='', outline=color, width=1)

        # Status LED dot
        led_col = color if is_active else '#223344'
        c.create_oval(x - 4, fy - 94, x + 4, fy - 86, fill=led_col, outline='')

        # Label
        c.create_text(x, fy + 14, text=label, fill=color,
                      font=('Courier', 8, 'bold'), anchor='n', justify='center')

    def _draw_stickman(self, x: int):
        c       = self._canvas
        floor   = STICK_FLOOR_Y
        col     = self._state_color()
        walking = self._walk_speed != 0
        sc      = self._scale   # current visual scale

        # Scale all body dimensions from the floor anchor
        head_r   = int(STICK_HEAD_R   * sc)
        body_len = int(STICK_BODY_LEN * sc)
        leg_len  = int(STICK_LEG_LEN  * sc)
        arm_len  = int(STICK_ARM_LEN  * sc)
        sw_amp   = STICKMAN_SWING_AMPLITUDE * sc

        # Shadow ellipse — wider when scaled up (closer = bigger shadow)
        shadow_w = int((28 if walking else 22) * sc)
        shadow_h = int(8 * sc)
        c.create_oval(x - shadow_w, floor + 2,
                      x + shadow_w, floor + 2 + shadow_h,
                      fill='#0a1820', outline='')

        swing = math.sin(self._walk_phase) * sw_amp if walking else 0

        # Key Y positions (all scaled from floor upward)
        head_cy  = floor - leg_len - body_len - head_r
        neck_y   = head_cy + head_r
        hip_y    = neck_y  + body_len
        arm_py   = neck_y  + int(body_len * 0.30)
        shoulder_w = int(10 * sc)
        hip_w      = int(7  * sc)

        dir_ = self._walk_speed if self._walk_speed != 0 else 1
        fa   =  swing * STICKMAN_ARM_SWING_FACTOR * dir_
        ba   = -swing * STICKMAN_ARM_SWING_FACTOR * dir_
        ll   =  int(swing * STICKMAN_LEG_SWING_FACTOR)
        rl   = -ll

        # ── Glow rings around head when active ──────────────────────────
        if self._state != 'idle':
            pulse  = (math.sin(self._pulse_t * 4) + 1) * 0.5
            glow_r = head_r + int((6 + pulse * 5) * sc)
            c.create_oval(x - glow_r, head_cy - glow_r,
                          x + glow_r, head_cy + glow_r,
                          fill='', outline=col, width=1)

        # Extra outer ring for crossing state (person is "close")
        if self._state == 'crossing':
            pulse2 = (math.sin(self._pulse_t * 3 + 1.5) + 1) * 0.5
            ring2  = head_r + int((16 + pulse2 * 10) * sc)
            c.create_oval(x - ring2, head_cy - ring2,
                          x + ring2, head_cy + ring2,
                          fill='', outline=self._dim_color(col, 0.35), width=2)

        # ── Head ────────────────────────────────────────────────────────
        c.create_oval(x - head_r - int(3*sc), head_cy - head_r - int(3*sc),
                      x + head_r + int(3*sc), head_cy + head_r + int(3*sc),
                      fill='#0d1a25', outline=col, width=1)
        c.create_oval(x - head_r, head_cy - head_r,
                      x + head_r, head_cy + head_r,
                      fill='#111e2a', outline=col, width=max(2, int(2*sc)))

        # Eyes — scale their offset
        eye_off = int(8 * sc)
        eye_r   = max(2, int(3 * sc))
        eye_y   = head_cy - int(4 * sc)
        c.create_oval(x - eye_off - eye_r, eye_y - eye_r,
                      x - eye_off + eye_r, eye_y + eye_r, fill=col, outline='')
        c.create_oval(x + eye_off - eye_r, eye_y - eye_r,
                      x + eye_off + eye_r, eye_y + eye_r, fill=col, outline='')

        # Mouth
        mo = int(4 * sc)
        if self._state in ('at_left', 'at_right'):
            c.create_arc(x - mo*2, head_cy + mo,
                         x + mo*2, head_cy + mo*4,
                         start=200, extent=140, style='arc', outline=col, width=1)
        elif self._state == 'crossing':
            # Surprised "O" — scaled
            c.create_oval(x - int(6*sc), head_cy + int(4*sc),
                          x + int(6*sc), head_cy + int(13*sc),
                          outline=col, fill='', width=max(1, int(1.5*sc)))

        # ── Neck ────────────────────────────────────────────────────────
        c.create_line(x, neck_y, x, neck_y + int(8*sc),
                      fill=col, width=max(2, int(2*sc)))

        # ── Body (tapered torso) ─────────────────────────────────────────
        c.create_polygon(
            x - shoulder_w, neck_y + int(8*sc),
            x + shoulder_w, neck_y + int(8*sc),
            x + hip_w,      hip_y,
            x - hip_w,      hip_y,
            outline=col, fill='#0d1a25', width=max(2, int(2*sc)))
        c.create_line(x, neck_y + int(10*sc), x, hip_y - int(6*sc),
                      fill=col, width=1)

        # ── Arms ────────────────────────────────────────────────────────
        arm_ext = int(arm_len * 0.75)
        lax = x - arm_ext;  lhand_y = int(arm_py + fa)
        rax = x + arm_ext;  rhand_y = int(arm_py + ba)

        c.create_line(x - shoulder_w, arm_py, lax, lhand_y,
                      fill=col, width=max(2, int(2*sc)), capstyle='round')
        hand_r = max(3, int(3*sc))
        c.create_oval(lax - hand_r, lhand_y - hand_r,
                      lax + hand_r, lhand_y + hand_r, fill=col, outline='')

        c.create_line(x + shoulder_w, arm_py, rax, rhand_y,
                      fill=col, width=max(2, int(2*sc)), capstyle='round')
        c.create_oval(rax - hand_r, rhand_y - hand_r,
                      rax + hand_r, rhand_y + hand_r, fill=col, outline='')

        # ── Legs (two segments with knee bend) ──────────────────────────
        bend = int(abs(swing) * 0.35) if walking else 0

        lkx = x + ll // 2;  lky = hip_y + leg_len // 2 - bend
        c.create_line(x - hip_w, hip_y, lkx, lky,
                      fill=col, width=max(2, int(2*sc)), capstyle='round')
        c.create_line(lkx, lky, x + ll, floor,
                      fill=col, width=max(2, int(2*sc)), capstyle='round')
        fd  = 1 if ll >= 0 else -1
        c.create_line(x+ll, floor, x+ll+fd*int(10*sc), floor,
                      fill=col, width=max(3, int(3*sc)), capstyle='round')

        rkx = x + rl // 2;  rky = hip_y + leg_len // 2 - bend
        c.create_line(x + hip_w, hip_y, rkx, rky,
                      fill=col, width=max(2, int(2*sc)), capstyle='round')
        c.create_line(rkx, rky, x + rl, floor,
                      fill=col, width=max(2, int(2*sc)), capstyle='round')
        fd2 = 1 if rl >= 0 else -1
        c.create_line(x+rl, floor, x+rl+fd2*int(10*sc), floor,
                      fill=col, width=max(3, int(3*sc)), capstyle='round')

        # ── Direction arrow (only while walking) ────────────────────────
        if self._walk_speed != 0:
            ay  = head_cy - head_r - int(18 * sc)
            ax2 = x + int(STICKMAN_ARROW_LENGTH * self._walk_speed * sc)
            pulse_i = int((math.sin(self._pulse_t * 5) + 1) * 1.5)
            c.create_line(x, ay, ax2, ay, fill=col,
                          width=2 + pulse_i, arrow=tk.LAST,
                          arrowshape=(int(10*sc), int(14*sc), int(5*sc)))
            step = int(STICKMAN_ARROW_LENGTH * sc) // 3
            for k in range(1, 3):
                cx_ = x + int(step * k * self._walk_speed)
                c.create_line(cx_ - int(4*sc) * self._walk_speed, ay - int(4*sc),
                               cx_, ay,
                               cx_ - int(4*sc) * self._walk_speed, ay + int(4*sc),
                               fill=col, width=1)

    def _draw_scene(self):
        c = self._canvas
        c.delete('all')

        self._pulse_t += 0.08

        self._draw_background()
        self._draw_floor()

        conf_a = self.det_a.confirmed_low
        conf_b = self.det_b.confirmed_low

        self._draw_node(STICK_NODE_A_X,
                        f"Node A\n:{UDP_PORT_A}", COLOR_AT_LEFT,  conf_a)
        self._draw_node(STICK_NODE_B_X,
                        f"Node B\n:{UDP_PORT_B}", COLOR_AT_RIGHT, conf_b)

        self._draw_stickman(int(self._x))

    def _draw_streak_bars(self):
        c     = self._streak_canvas
        c.delete('all')
        W     = STICK_WIN_W
        BAR_H = 12
        MAX_W = (W // 2) - 38

        sa = self.det_a.streak
        sb = self.det_b.streak

        # ── Node A bar ──
        fill_a = min(sa / CONFIRMATION_STREAK, 1.0)
        _draw_filled_rounded_rect(c, 10, 2, 10 + MAX_W, 2 + BAR_H, 4,
                                   fill=COLOR_STREAK_A_BG, outline=COLOR_STREAK_A_OUTLINE)
        if fill_a > 0:
            bar_w = max(8, int(MAX_W * fill_a))
            _draw_filled_rounded_rect(c, 10, 2, 10 + bar_w, 2 + BAR_H, 4,
                                       fill=COLOR_STREAK_A_FULL if fill_a >= 1.0 else COLOR_STREAK_A_FILL,
                                       outline='')
        c.create_text(10 + MAX_W + 8, 2 + BAR_H // 2,
                      text=f"A {sa:02d}/{CONFIRMATION_STREAK}",
                      fill=COLOR_AT_LEFT, font=('Courier', 8, 'bold'), anchor='w')

        # ── Node B bar ──
        fill_b = min(sb / CONFIRMATION_STREAK, 1.0)
        mid = W // 2 + 4
        _draw_filled_rounded_rect(c, mid, 2, mid + MAX_W, 2 + BAR_H, 4,
                                   fill=COLOR_STREAK_B_BG, outline=COLOR_STREAK_B_OUTLINE)
        if fill_b > 0:
            bar_w = max(8, int(MAX_W * fill_b))
            _draw_filled_rounded_rect(c, mid, 2, mid + bar_w, 2 + BAR_H, 4,
                                       fill=COLOR_STREAK_B_FULL if fill_b >= 1.0 else COLOR_STREAK_B_FILL,
                                       outline='')
        c.create_text(mid + MAX_W + 8, 2 + BAR_H // 2,
                      text=f"B {sb:02d}/{CONFIRMATION_STREAK}",
                      fill=COLOR_AT_RIGHT, font=('Courier', 8, 'bold'), anchor='w')

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------
    def _update(self):
        if not self._running:
            return

        da = self.de_a.current_digit()
        db = self.de_b.current_digit()

        conf_a = self.det_a.update(da)
        conf_b = self.det_b.update(db)

        self._direction = self.dir_tracker.update(conf_a, conf_b, da, db)
        self._state     = self._compute_state(conf_a, conf_b, self._direction)

        self._target_x, self._walk_speed, self._target_scale = self._target_for_state(self._state)

        lerp = STICKMAN_LERP_WALK if self._state in ('moving_right', 'moving_left') \
               else STICKMAN_LERP_IDLE
        self._x     += (self._target_x     - self._x)     * lerp
        self._scale += (self._target_scale - self._scale) * STICKMAN_LERP_IDLE

        if abs(self._walk_speed) > 0:
            self._walk_phase += STICKMAN_WALK_PHASE_STEP
        else:
            if abs(self._walk_phase % math.pi) > 0.15:
                self._walk_phase += STICKMAN_POSE_DAMP_STEP

        self._draw_scene()
        self._draw_streak_bars()

        STATUS_MAP = {
            'idle':         '○  No motion detected',
            'at_left':      f'◉  Person confirmed at Node A  (streak ≥ {CONFIRMATION_STREAK})',
            'at_right':     f'◉  Person confirmed at Node B  (streak ≥ {CONFIRMATION_STREAK})',
            'moving_right': '▶  Moving right  A → B',
            'moving_left':  '◀  Moving left   B → A',
            'crossing':     '⊗  Crossing / between nodes',
        }
        self._status_var.set(STATUS_MAP.get(self._state, ''))

        self._da_var.set(f"A: {da:.1f}" if not math.isnan(da) else "A: –")
        self._db_var.set(f"B: {db:.1f}" if not math.isnan(db) else "B: –")

        DT = DirectionTracker
        dir_label = {DT.A_TO_B: "A → B", DT.B_TO_A: "B → A", DT.NONE: "–"}
        self._dir_var.set(f"dir: {dir_label[self._direction]}")


def launch_stickman_window(de_a: DigitExtractor, de_b: DigitExtractor):
    StickmanWindow(de_a, de_b).launch()


# ==========================================
# TIME-GRID HELPER
# ==========================================
def build_time_grid(csi: np.ndarray, times: np.ndarray) -> np.ndarray:
    if csi.size == 0 or len(times) == 0:
        return np.full((MAX_SUBCARRIERS, HISTORY_SIZE), np.nan)
    now  = time.time()
    t0   = now - TIME_WINDOW
    grid = np.full((MAX_SUBCARRIERS, HISTORY_SIZE), np.nan, dtype=np.float32)
    x_idx = ((times - t0) / TIME_WINDOW * (HISTORY_SIZE - 1)).astype(int)
    for i, x in enumerate(x_idx):
        if 0 <= x < HISTORY_SIZE:
            grid[:, x] = csi[:, i]
    return grid


# ==========================================
# VISUALIZER  —  dual heatmap + digit graph
# ==========================================
def start_monitor(rx_a: BinaryCSIReceiver,
                  rx_b: BinaryCSIReceiver,
                  mask:  SubcarrierMask):

    plt.style.use('dark_background')
    fig = plt.figure(figsize=FIGURE_SIZE)
    fig.canvas.manager.set_window_title('ESP32 CSI Monitor — Dual Node')

    gs = gridspec.GridSpec(5, 1,
                           height_ratios=[3, 3, 1, 1.4, 0.3],
                           hspace=0.42)
    ax_a = plt.subplot(gs[0])
    ax_b = plt.subplot(gs[1])
    ax_r = plt.subplot(gs[2])
    ax_d = plt.subplot(gs[3])
    ax_s = plt.subplot(gs[4])

    def make_heatmap(ax, title_str, title_color):
        ax.set_title(title_str, fontsize=12, fontweight='bold', color=title_color)
        im = ax.imshow(np.zeros((MAX_SUBCARRIERS, HISTORY_SIZE)),
                       aspect='auto', cmap=HEATMAP_CMAP,
                       vmin=HEATMAP_VMIN, vmax=HEATMAP_VMAX,
                       animated=True, interpolation=HEATMAP_INTERPOLATION)
        ax.set_ylabel("Subcarrier", fontsize=9)
        ax.set_yticks(np.arange(0, MAX_SUBCARRIERS, 8))
        ax.tick_params(axis='both', labelsize=8)
        cbar = plt.colorbar(im, ax=ax, pad=0.01, fraction=0.015)
        cbar.set_label('Amplitude', rotation=270, labelpad=12, fontsize=8)
        cbar.ax.tick_params(labelsize=7)
        return im

    img_a = make_heatmap(ax_a, f"Node A — port {UDP_PORT_A}", COLOR_AT_LEFT)
    img_b = make_heatmap(ax_b, f"Node B — port {UDP_PORT_B}", COLOR_AT_RIGHT)
    ax_b.set_xlabel(f"Time (last {TIME_WINDOW:.0f}s) →", fontsize=9)

    ax_r.set_title("RSSI  (dBm)", fontsize=8, color='white', pad=2)
    ax_r.set_xlim(0, HISTORY_SIZE)
    ax_r.set_ylim(RSSI_YLIM_MIN, RSSI_YLIM_MAX)
    ax_r.tick_params(axis='both', labelsize=7)
    ax_r.grid(True, linestyle='--', alpha=0.2, color='gray')
    line_rssi_a, = ax_r.plot([], [], color=COLOR_AT_LEFT,  lw=1, alpha=0.8, label=f'A ({UDP_PORT_A})')
    line_rssi_b, = ax_r.plot([], [], color=COLOR_AT_RIGHT, lw=1, alpha=0.8, label=f'B ({UDP_PORT_B})')
    ax_r.legend(loc='upper left', fontsize=7, framealpha=0.3)

    ax_d.set_title(
        "Single-Digit Feature  (0–9)  —  rolling-normalised median amplitude",
        fontsize=9, color='white', pad=3)
    ax_d.set_xlim(0, DIGIT_HISTORY)
    ax_d.set_ylim(-0.5, 9.5)
    ax_d.set_yticks(range(10))
    ax_d.tick_params(axis='both', labelsize=7)
    ax_d.grid(True, linestyle='--', alpha=0.18, color='gray')
    ax_d.set_ylabel("Digit", fontsize=8)

    line_digit_a, = ax_d.plot([], [], color=COLOR_AT_LEFT,  lw=1.5, alpha=0.85, label=f'A ({UDP_PORT_A})')
    line_digit_b, = ax_d.plot([], [], color=COLOR_AT_RIGHT, lw=1.5, alpha=0.85, label=f'B ({UDP_PORT_B})')

    for y in range(10): ax_d.axhline(y, color='gray', lw=0.3, alpha=0.3)
    ax_d.axhline(PRESENCE_THRESHOLD, color='#ff4444', lw=1, linestyle='--', alpha=0.7,
                 label=f'enter {PRESENCE_THRESHOLD} / exit {PRESENCE_HYSTERESIS_HI}  (×{CONFIRMATION_STREAK} streak)')
    ax_d.axhline(PRESENCE_HYSTERESIS_HI, color='#ff8866', lw=0.8, linestyle=':', alpha=0.5)

    badge_a = ax_d.text(DIGIT_HISTORY * 0.02, 8.5, "A: –", color=COLOR_AT_LEFT,
                        fontsize=11, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', fc='#001a1a', ec=COLOR_AT_LEFT, alpha=0.8))
    badge_b = ax_d.text(DIGIT_HISTORY * 0.15, 8.5, "B: –", color=COLOR_AT_RIGHT,
                        fontsize=11, fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.3', fc='#1a0d00', ec=COLOR_AT_RIGHT, alpha=0.8))
    ax_d.legend(loc='upper right', fontsize=7, framealpha=0.3)

    ax_s.axis('off')
    txt_stats = ax_s.text(0.5, 0.5, "Initializing...",
                          transform=ax_s.transAxes, ha='center', va='center',
                          fontsize=9, color='yellow', fontweight='bold',
                          bbox=dict(boxstyle='round', facecolor='black', alpha=0.8))

    de_a = DigitExtractor()
    de_b = DigitExtractor()

    threading.Thread(target=launch_stickman_window,
                     args=(de_a, de_b), daemon=True).start()
    print("🚶 Stickman motion window opened.")

    x_digit = np.arange(DIGIT_HISTORY)

    def apply_mask(csi_grid):
        active = mask.get_all()
        m = csi_grid.astype(np.float32).copy()
        for sc in range(MAX_SUBCARRIERS):
            if not active[sc]: m[sc, :] = np.nan
        return m

    def map_time_to_x(times):
        now = time.time()
        return (times - (now - TIME_WINDOW)) / TIME_WINDOW * (HISTORY_SIZE - 1)

    def update(frame_idx):
        csi_a, rssi_a, t_a, pps_a, alive_a = rx_a.get_data()
        csi_b, rssi_b, t_b, pps_b, alive_b = rx_b.get_data()
        active_mask = mask.get_all()

        if csi_a.shape[1] > 0:
            grid_a = apply_mask(build_time_grid(csi_a, t_a))
            img_a.cmap.set_bad(HEATMAP_NULL_COLOR)
            img_a.set_data(grid_a)
            if frame_idx % HEATMAP_AUTOSCALE_INTERVAL == 0:
                vis = grid_a[~np.isnan(grid_a)]
                if vis.size > 0:
                    img_a.set_clim(0, max(np.percentile(vis, HEATMAP_AUTOSCALE_PERCENTILE), 10))
            de_a.push(csi_a[:, -1], active_mask)
        else:
            de_a.digit_history.append(np.nan)

        if csi_b.shape[1] > 0:
            grid_b = apply_mask(build_time_grid(csi_b, t_b))
            img_b.cmap.set_bad(HEATMAP_NULL_COLOR)
            img_b.set_data(grid_b)
            if frame_idx % HEATMAP_AUTOSCALE_INTERVAL == 0:
                vis = grid_b[~np.isnan(grid_b)]
                if vis.size > 0:
                    img_b.set_clim(0, max(np.percentile(vis, HEATMAP_AUTOSCALE_PERCENTILE), 10))
            de_b.push(csi_b[:, -1], active_mask)
        else:
            de_b.digit_history.append(np.nan)

        if len(t_a) > 0: line_rssi_a.set_data(map_time_to_x(t_a), rssi_a)
        if len(t_b) > 0: line_rssi_b.set_data(map_time_to_x(t_b), rssi_b)

        if frame_idx % HEATMAP_AUTOSCALE_INTERVAL == 0:
            all_rssi = []
            if rssi_a.size > 0: all_rssi.extend(rssi_a.tolist())
            if rssi_b.size > 0: all_rssi.extend(rssi_b.tolist())
            if all_rssi:
                r   = max(all_rssi) - min(all_rssi)
                pad = max(RSSI_AUTOSCALE_PAD, r * RSSI_AUTOSCALE_PAD_FRACTION)
                ax_r.set_ylim(max(min(all_rssi) - pad, -100),
                              min(max(all_rssi) + pad, 0))

        digs_a = np.array(de_a.digit_history)
        digs_b = np.array(de_b.digit_history)
        line_digit_a.set_data(x_digit, digs_a)
        line_digit_b.set_data(x_digit, digs_b)

        cur_a = digs_a[~np.isnan(digs_a)]
        cur_b = digs_b[~np.isnan(digs_b)]
        badge_a.set_text(f"A: {cur_a[-1]:.1f}" if cur_a.size > 0 else "A: –")
        badge_b.set_text(f"B: {cur_b[-1]:.1f}" if cur_b.size > 0 else "B: –")

        def rssi_str(rssi, alive):
            if not alive:      return "NO SIGNAL"
            if rssi.size == 0: return " –99 dBm"
            return f"{rssi[-1]:+.0f} dBm"

        sa = "🟢" if alive_a else "🔴"
        sb = "🟢" if alive_b else "🔴"
        txt_stats.set_text(
            f"{sa} A:{UDP_PORT_A}  PPS:{pps_a:3d}  RSSI:{rssi_str(rssi_a, alive_a)}   "
            f"{sb} B:{UDP_PORT_B}  PPS:{pps_b:3d}  RSSI:{rssi_str(rssi_b, alive_b)}   "
            f"| SC shown: {sum(active_mask)}/{MAX_SUBCARRIERS}"
        )

        return img_a, img_b, line_rssi_a, line_rssi_b, \
               line_digit_a, line_digit_b, badge_a, badge_b, txt_stats

    ani = FuncAnimation(fig, update, interval=ANIMATION_INTERVAL_MS,
                        blit=True, cache_frame_data=False)
    plt.tight_layout()

    import warnings
    warnings.filterwarnings('ignore', category=UserWarning)
    try:
        plt.show()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        rx_a.stop()
        rx_b.stop()


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("ESP32 CSI MONITOR  —  Dual Node  +  Stickman Motion")
    print("=" * 60)
    print(f"  Node A              : port {UDP_PORT_A}  (LEFT)")
    print(f"  Node B              : port {UDP_PORT_B}  (RIGHT)")
    print(f"  Presence threshold  : {PRESENCE_THRESHOLD} / 9  (exit at {PRESENCE_HYSTERESIS_HI})")
    print(f"  Confirmation streak : {CONFIRMATION_STREAK} frames")
    print(f"  Crossing scale      : {CROSSING_SCALE}×")
    print(f"  Streak decay (NaN)  : -{STREAK_DECAY_ON_NAN} /frame")
    print(f"  Move hold           : {MOVE_HOLD_FRAMES} frames")
    print(f"  Direction memory    : {DIRECTION_MEMORY_SEC}s")
    print(f"  Dir digit delta     : {DIRECTION_DIGIT_DELTA}")
    print(f"  EMA alpha           : {DIGIT_EMA_ALPHA}")
    print(f"  Norm window         : {DIGIT_NORM_WINDOW} frames")
    print(f"  Null SC threshold   : {NULL_THRESHOLD_FRACTION*100:.0f}% zeros")
    print("=" * 60)

    mask = SubcarrierMask()
    threading.Thread(target=launch_selector_window,
                     args=(mask,), daemon=True).start()
    print("🪟  Subcarrier selector window opened.")

    rx_a = BinaryCSIReceiver(UDP_PORT_A, label="Node A")
    rx_b = BinaryCSIReceiver(UDP_PORT_B, label="Node B")
    rx_a.start()
    rx_b.start()

    print(f"\n⏳ Waiting for {STARTUP_PACKET_WAIT} packets from at least one node "
          f"(timeout {STARTUP_TIMEOUT_SEC}s)...")
    t0 = time.time()
    while rx_a.packet_count < STARTUP_PACKET_WAIT and rx_b.packet_count < STARTUP_PACKET_WAIT:
        if time.time() - t0 > STARTUP_TIMEOUT_SEC:
            print(f"\n❌ Timeout — no packets on either port after {STARTUP_TIMEOUT_SEC}s")
            rx_a.stop(); rx_b.stop()
            exit(1)
        time.sleep(0.1)

    print(f"✅ Receiving!  A: {rx_a.packet_count} pkts   B: {rx_b.packet_count} pkts")
    print("🎨 Starting visualization...\n")
    start_monitor(rx_a, rx_b, mask)
