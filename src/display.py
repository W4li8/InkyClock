"""
display.py -- Pico Inky Pack interface.

Wraps picographics.PicoGraphics(DISPLAY_INKY_PACK) with the views this
project needs: the big centered 24h clock, the alarm-set digit editor, the
press-C alarm preview, and the alarm-ringing border flash.

show_clock/show_alarm_edit/show_alarm_preview are deliberately "a coherent
display": all three share _big_time_layout() so the big HH:MM sits at the
exact same position/size in every one of them, and only the row underneath
changes content -- the date (clock), a static digit-selection cursor
(edit), or the alarm's ON/OFF state (preview). Switching between them
should read as one screen changing state, not three different screens.

To change layout (margins, font, how big the clock gets) see the constants
and _big_time_layout() below. Sizes are computed at runtime from
picographics.measure_text() so they adapt to the real font metrics, but the
text-height estimate (FONT_CELL_PX) is a nominal guess for the "bitmap8"
font -- nudge it if the clock looks smaller/bigger than intended on real
hardware.
"""

import time

from picographics import PicoGraphics, DISPLAY_INKY_PACK

BLACK = 0
WHITE = 15

FONT = "bitmap8"
FONT_CELL_PX = 8          # bitmap8's nominal glyph cell, used to estimate text height
MARGIN_PX = 10            # side/vertical margin kept clear around the big clock
SUBLINE_SCALE = 2         # font for the row under the clock: date / cursor / "ALARM ON/OFF"
SUBLINE_GAP_PX = 6        # gap between the big clock and that row
CURSOR_THICKNESS_PX = 4   # edit-mode digit-selection underline thickness
CURSOR_PAD_FRACTION = 0.25  # extra width added each side of the cursor, as a
                            # fraction of the font's own inter-character gap
                            # -- see show_alarm_edit; trades pixel-perfect
                            # tightness for a visibly wider, still-centered bar
BORDER_THICKNESS_PX = 6   # alarm-ring flash border thickness

# Confirmed on real hardware: mashing buttons fast enough to call
# graphics.update() again before the panel has physically finished its
# previous refresh can crash the driver (not just look glitchy). Every view
# method below only draws into the in-memory buffer (fast, no hardware
# wait); main.py calls push_if_due() once per loop tick to actually push to
# the panel, which enforces this floor WITHOUT blocking button polling --
# see push_if_due()'s docstring for why blocking there was itself a bug.
# 500ms is a conservative floor, not a measured spec sheet number
# (Pimoroni doesn't publish one for set_update_speed(3)); raise it if a
# crash is ever seen again.
MIN_UPDATE_INTERVAL_MS = 500

# RTC weekday convention this project uses (0=Monday..6=Sunday) -- must match
# wifi.py's _WEEKDAY_FROM_NAME, which is what actually sets this value on the RTC.
_WEEKDAY_ABBR = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


class InkyDisplay:
    def __init__(self):
        self.graphics = PicoGraphics(DISPLAY_INKY_PACK)
        self.width, self.height = self.graphics.get_bounds()
        self.graphics.set_update_speed(3)  # fastest refresh Pimoroni's driver offers
        self.graphics.set_font(FONT)
        self._last_update_ticks = None
        self._dirty = False

    # -- low level helpers ----------------------------------------------
    def push_if_due(self):
        """
        Non-blocking: push the currently-drawn buffer to the panel if
        there's unpushed content AND MIN_UPDATE_INTERVAL_MS has elapsed
        since the last push; otherwise return immediately without waiting.
        main.py calls this once per loop tick, right after the mode
        dispatch -- view methods below only ever draw into the buffer,
        never push directly.

        This isn't just an efficiency nicety: the previous design
        (blocking inside every view method until the throttle window
        passed) caused a real, reported regression -- "feels like I need
        two clicks for anything" in edit mode. A full button press+release
        happening entirely during that block is invisible to
        poll_button()'s edge-detection, since main.py's loop wasn't
        running at all during the wait. Coalescing rapid draws into a
        single push once the panel's actually due, without ever blocking
        button polling in between, fixed it. (The single unavoidable
        blocking window left is the real hardware push itself, when it
        does fire -- that's a physical constraint, not a design choice.)

        Returns True if it actually pushed.
        """
        if not self._dirty:
            return False
        now = time.ticks_ms()
        if self._last_update_ticks is not None:
            if time.ticks_diff(now, self._last_update_ticks) < MIN_UPDATE_INTERVAL_MS:
                return False
        self.graphics.update()
        self._last_update_ticks = time.ticks_ms()
        self._dirty = False
        return True

    def _fit_scale(self, text, max_w, max_h, max_scale=20, min_scale=1):
        """
        Largest INTEGER scale for `text` that fits inside max_w x max_h.
        Integer only, not just for a coarser-but-fine visual step: confirmed
        on real hardware that PicoGraphics.text() raises TypeError on a
        float scale, even though measure_text() silently accepts one --
        searching in integer steps keeps the width used here (for centering)
        consistent with what actually gets rendered.
        """
        scale = max_scale
        while scale > min_scale:
            w = self.graphics.measure_text(text, scale)
            h_est = FONT_CELL_PX * scale
            if w <= max_w and h_est <= max_h:
                return scale
            scale -= 1
        return min_scale

    def _clear(self):
        self.graphics.set_pen(WHITE)
        self.graphics.clear()
        self.graphics.set_pen(BLACK)
        self._dirty = True

    def _draw_centered(self, text, y, scale):
        w = self.graphics.measure_text(text, scale)
        x = int((self.width - w) / 2)
        self.graphics.text(text, x, y, scale=scale)
        return x, w

    def _big_time_layout(self, time_text):
        """
        Shared layout math for the big HH:MM + sub-line row used by
        show_clock, show_alarm_edit, and show_alarm_preview -- factored out
        so those three are guaranteed pixel-identical for the time's
        position/size (the point of them being "a coherent display"; only
        the sub-line's content differs between them).
        Returns (scale, top_y, sub_line_y).
        """
        sub_h = FONT_CELL_PX * SUBLINE_SCALE + SUBLINE_GAP_PX
        max_w = self.width - 2 * MARGIN_PX
        max_h = self.height - 2 * MARGIN_PX - sub_h
        scale = self._fit_scale(time_text, max_w, max_h)
        clock_h = FONT_CELL_PX * scale
        top_y = int((self.height - (clock_h + sub_h)) / 2)
        sub_line_y = top_y + clock_h + SUBLINE_GAP_PX
        return scale, top_y, sub_line_y

    def _digit_spacing(self, scale):
        """
        The font's own inter-character gap at this scale, measured (not
        assumed) as measure_text('00') - 2*measure_text('0') -- confirmed
        live that this equals `scale` exactly (i.e. one base-font pixel of
        spacing, scaled), but derived from the font instead of hardcoded in
        case that ever isn't true for a different font/scale.
        """
        return self.graphics.measure_text("00", scale) - 2 * self.graphics.measure_text("0", scale)

    def _draw_time_with_dots(self, hour, minute, top_y, scale):
        """
        Draw a big "HH:MM" with the colon as two small square dots rather
        than the bitmap font's own ':' glyph (which renders as tall blocks
        at scale, not dots). "HH" and "MM" are drawn as two independently
        measured 2-character segments with an explicit, known gap between
        them, rather than one 5-character string -- besides making the dot
        gap trivial to size, this is what makes show_alarm_edit's digit
        cursor line up reliably: the font's actual inter-character spacing
        around a ':' character turned out ambiguous to reason about across
        a whole "HH:MM" string, but is unambiguous within a plain 2-digit
        segment (see _digit_spacing).
        Returns (hh_x, mm_x) -- segment left edges, for the cursor math in
        show_alarm_edit.
        """
        hh_text = f"{hour:02}"
        mm_text = f"{minute:02}"
        hh_w = self.graphics.measure_text(hh_text, scale)
        mm_w = self.graphics.measure_text(mm_text, scale)
        dot_size = max(2, scale)
        spacing = self._digit_spacing(scale)
        # Equal spacing (the font's own inter-digit gap) on each side of the
        # dot, matching the HH/MM internal digit spacing -- was previously
        # just measure_text(":"), which sat right up against the digits.
        dot_gap_w = spacing + dot_size + spacing

        total_w = hh_w + dot_gap_w + mm_w
        hh_x = int((self.width - total_w) / 2)
        mm_x = hh_x + hh_w + dot_gap_w

        self.graphics.text(hh_text, hh_x, top_y, scale=scale)
        self.graphics.text(mm_text, mm_x, top_y, scale=scale)

        dot_x = hh_x + hh_w + spacing
        cell_h = FONT_CELL_PX * scale
        self.graphics.rectangle(dot_x, top_y + cell_h // 3 - dot_size // 2, dot_size, dot_size)
        self.graphics.rectangle(dot_x, top_y + (cell_h * 2) // 3 - dot_size // 2, dot_size, dot_size)

        return hh_x, mm_x

    # -- views ---------------------------------------------------------
    def show_clock(self, hour, minute, year=None, month=None, day=None, weekday=None, alarm_enabled=True):
        """
        Big centered 24h HH:MM clock, occupying most of the screen. If a
        date is given, a "Sat 27/09/26"-style sub-line is drawn underneath
        it (weekday name omitted if `weekday` isn't given) -- called from
        main.py every time the RTC-driven minute changes (which includes a
        resync moving the date), see main.py's minute_key.

        alarm_enabled=False (long-press C, see alarm.py) draws a small
        "ALARM OFF" label in the corner instead of leaving no indicator --
        deliberately unobtrusive so the clock still "occupies most of the
        space" when the alarm is on, which is the common case. (Pressing C
        for a fuller ON/OFF readout in the sub-line row is show_alarm_preview.)
        """
        print(f"[display] show_clock {hour:02}:{minute:02} date={year}-{month}-{day} alarm_enabled={alarm_enabled}")
        time_text = f"{hour:02}:{minute:02}"
        date_text = None
        if year is not None:
            date_text = f"{day:02}/{month:02}/{year % 100:02}"
            if weekday is not None and 0 <= weekday <= 6:
                date_text = f"{_WEEKDAY_ABBR[weekday]} {date_text}"

        self._clear()
        scale, top_y, sub_line_y = self._big_time_layout(time_text)
        self._draw_time_with_dots(hour, minute, top_y, scale)
        if date_text:
            self._draw_centered(date_text, sub_line_y, SUBLINE_SCALE)

        if not alarm_enabled:
            self.graphics.text("ALARM OFF", MARGIN_PX, MARGIN_PX, scale=1)

    def show_alarm_preview(self, hour, minute, alarm_enabled):
        """
        Press-C preview (see alarm.py Alarm.start_preview / main.py
        MODE_PREVIEW): the alarm's set time, positioned/sized exactly like
        show_clock, with the sub-line row showing "ALARM ON"/"ALARM OFF"
        instead of the date -- shows the current state immediately on
        press, and reflects the toggle the instant it fires (holding the
        full config.ALARM_LONG_PRESS_S window, see main.py's c_long).
        """
        print(f"[display] show_alarm_preview {hour:02}:{minute:02} enabled={alarm_enabled}")
        time_text = f"{hour:02}:{minute:02}"
        state_text = "ALARM ON" if alarm_enabled else "ALARM OFF"

        self._clear()
        scale, top_y, sub_line_y = self._big_time_layout(time_text)
        self._draw_time_with_dots(hour, minute, top_y, scale)
        self._draw_centered(state_text, sub_line_y, SUBLINE_SCALE)

    def show_alarm_edit(self, hour, minute, digit_index):
        """
        Alarm-set view: the alarm's HH:MM positioned/sized exactly like
        show_clock, with a static underline cursor in the sub-line row
        under whichever digit (0=hour tens .. 3=minute ones) is currently
        selected -- see alarm.py's Alarm.digit_index / next_digit.

        Static rather than blinking, deliberately: a periodic blink meant a
        full e-ink redraw every tick even with no input, which was a real,
        noticeable UX problem on this panel. A static cursor only needs a
        redraw when digit_index/hour/minute actually change (main.py's
        edit_state cache already gates on exactly that).
        """
        print(f"[display] show_alarm_edit {hour:02}:{minute:02} digit_index={digit_index}")
        time_text = f"{hour:02}:{minute:02}"  # only used for _big_time_layout's width budget/scale choice

        self._clear()
        scale, top_y, sub_line_y = self._big_time_layout(time_text)
        hh_x, mm_x = self._draw_time_with_dots(hour, minute, top_y, scale)

        # Which 2-char segment ("HH" or "MM") and which of its 2 digits
        # (local_index 0 or 1) digit_index refers to.
        if digit_index < 2:
            segment_text, segment_x, local_index = f"{hour:02}", hh_x, digit_index
        else:
            segment_text, segment_x, local_index = f"{minute:02}", mm_x, digit_index - 2

        # Tight glyph bounds for this one digit within its 2-char segment,
        # derived the same measured way as _digit_spacing (not assumed):
        # the font puts its inter-character gap BEFORE a non-first
        # character, not after the one before it -- confirmed by comparing
        # measure_text("0") to measure_text("07") - measure_text("0") on
        # real hardware, which is what let this be exact instead of a guess.
        spacing = self._digit_spacing(scale)
        prefix_w = self.graphics.measure_text(segment_text[:local_index], scale) if local_index > 0 else 0
        delta_w = self.graphics.measure_text(segment_text[:local_index + 1], scale) - prefix_w
        lead_gap = spacing if local_index > 0 else 0
        tight_x0 = prefix_w + lead_gap
        tight_w = delta_w - lead_gap

        # Per the user: rather than chase pixel-perfect tightness, pad the
        # cursor by CURSOR_PAD_FRACTION of the font's own inter-character
        # gap on each side, staying centered on the digit -- wider and more
        # visible, still unambiguously "this digit".
        pad = int(spacing * CURSOR_PAD_FRACTION)
        cursor_x0 = segment_x + tight_x0 - pad
        cursor_w = tight_w + 2 * pad

        for t in range(CURSOR_THICKNESS_PX):
            self.graphics.line(cursor_x0, sub_line_y + t, cursor_x0 + cursor_w, sub_line_y + t)

    def flash_alarm_border(self, hour, minute, border_visible):
        """
        Alarm-ringing view: keeps the alarm's HH:MM on screen and toggles a
        thick border around the edge. Driven by main.py's ring loop at
        config.ALARM_RING_FLASH_HZ.

        Note: a full e-ink refresh on this panel typically takes longer than
        a 2 Hz toggle (250ms per state) allows, so the achieved flash rate
        will end up throttled by the panel's own refresh time rather than
        truly hitting 2 Hz -- see docs/buzzer-notes.md. This is a placeholder
        for the real alarm signal (the buzzer) anyway, see buzzer.py.
        """
        print(f"[display] flash_alarm_border {hour:02}:{minute:02} border_visible={border_visible}")
        text = f"{hour:02}:{minute:02}"
        self._clear()
        max_w = self.width - 2 * (MARGIN_PX + BORDER_THICKNESS_PX)
        max_h = self.height - 2 * (MARGIN_PX + BORDER_THICKNESS_PX)
        scale = self._fit_scale(text, max_w, max_h)
        y = int((self.height - FONT_CELL_PX * scale) / 2)
        self._draw_centered(text, y, scale)

        if border_visible:
            for t in range(BORDER_THICKNESS_PX):
                self.graphics.line(t, t, self.width - 1 - t, t)                                       # top
                self.graphics.line(t, self.height - 1 - t, self.width - 1 - t, self.height - 1 - t)   # bottom
                self.graphics.line(t, t, t, self.height - 1 - t)                                      # left
                self.graphics.line(self.width - 1 - t, t, self.width - 1 - t, self.height - 1 - t)    # right

    def show_message(self, text):
        """
        Small utility view for boot/status messages (e.g. 'Syncing time...').
        Only draws -- like every other view now, push_if_due() does the
        actual push; main.py calls it once explicitly right after this at
        boot, since the main loop (which normally calls push_if_due() every
        tick) hasn't started yet.
        """
        print("[display] show_message:", text)
        self._clear()
        self.graphics.text(text, MARGIN_PX, self.height // 2 - 4, scale=1)
