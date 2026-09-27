"""
display.py -- Pico Inky Pack interface.

Wraps picographics.PicoGraphics(DISPLAY_INKY_PACK) with the views this
project needs: the big centered 24h clock (+ small date line), the
alarm-set digit editor, and the alarm-ringing border flash.

To change layout (margins, font, how big the clock gets, date format) see
the constants and show_clock() below. Sizes are computed at runtime from
picographics.measure_text() so they adapt to the real font metrics, but the
text-height estimate (FONT_CELL_PX) is a nominal guess for the "bitmap8"
font -- nudge it if the clock looks smaller/bigger than intended on real
hardware (this was written without a physical panel to check against).
"""

from picographics import PicoGraphics, DISPLAY_INKY_PACK

BLACK = 0
WHITE = 15

FONT = "bitmap8"
FONT_CELL_PX = 8          # bitmap8's nominal glyph cell, used to estimate text height
MARGIN_PX = 10            # side/vertical margin kept clear around the big clock
DATE_SCALE = 1            # small font for the DD/MM/YY sub-line
DATE_GAP_PX = 6           # gap between the clock and the date line
BORDER_THICKNESS_PX = 6   # alarm-ring flash border thickness


class InkyDisplay:
    def __init__(self):
        self.graphics = PicoGraphics(DISPLAY_INKY_PACK)
        self.width, self.height = self.graphics.get_bounds()
        self.graphics.set_update_speed(3)  # fastest refresh Pimoroni's driver offers
        self.graphics.set_font(FONT)

    # -- low level helpers ----------------------------------------------
    def _fit_scale(self, text, max_w, max_h, max_scale=20, min_scale=1, step=0.5):
        """Largest scale for `text` that fits inside max_w x max_h."""
        scale = max_scale
        while scale > min_scale:
            w = self.graphics.measure_text(text, scale)
            h_est = FONT_CELL_PX * scale
            if w <= max_w and h_est <= max_h:
                return scale
            scale -= step
        return min_scale

    def _clear(self):
        self.graphics.set_pen(WHITE)
        self.graphics.clear()
        self.graphics.set_pen(BLACK)

    def _draw_centered(self, text, y, scale):
        w = self.graphics.measure_text(text, scale)
        x = int((self.width - w) / 2)
        self.graphics.text(text, x, y, scale=scale)
        return x, w

    # -- views ---------------------------------------------------------
    def show_clock(self, hour, minute, year=None, month=None, day=None):
        """
        Big centered 24h HH:MM clock, occupying most of the screen. If a
        date is given, a smaller DD/MM/YY line is drawn underneath it --
        called from main.py every time the RTC-driven minute changes (which
        includes a resync moving the date), see main.py's minute_key.
        """
        time_text = "{:02}:{:02}".format(hour, minute)
        date_text = None
        if year is not None:
            date_text = "{:02}/{:02}/{:02}".format(day, month, year % 100)

        self._clear()

        date_h = (FONT_CELL_PX * DATE_SCALE + DATE_GAP_PX) if date_text else 0
        max_w = self.width - 2 * MARGIN_PX
        max_h = self.height - 2 * MARGIN_PX - date_h
        scale = self._fit_scale(time_text, max_w, max_h)
        clock_h = FONT_CELL_PX * scale

        total_h = clock_h + date_h
        top_y = int((self.height - total_h) / 2)
        self._draw_centered(time_text, top_y, scale)

        if date_text:
            date_y = top_y + clock_h + DATE_GAP_PX
            self._draw_centered(date_text, date_y, DATE_SCALE)

        self.graphics.update()

    def show_alarm_edit(self, hour, minute, digit_index, digit_visible):
        """
        Alarm-set view: same big HH:MM layout as show_clock, but for the
        alarm time being edited, with the digit at `digit_index` (0=hour
        tens .. 3=minute ones) blanked out when digit_visible is False to
        create the blink. See alarm.py for digit_index/blink-timing logic.
        """
        full_text = "{:02}:{:02}".format(hour, minute)
        chars = list(full_text)
        text_index = digit_index if digit_index < 2 else digit_index + 1  # skip the ':'
        if not digit_visible:
            chars[text_index] = " "
        text = "".join(chars)

        self._clear()
        hint_h = FONT_CELL_PX + 4
        max_w = self.width - 2 * MARGIN_PX
        max_h = self.height - 2 * MARGIN_PX - hint_h
        scale = self._fit_scale(full_text, max_w, max_h)
        y = MARGIN_PX
        self._draw_centered(text, y, scale)

        self.graphics.text("SET ALARM", MARGIN_PX, 2, scale=1)
        self.graphics.text("A- B:next C+", MARGIN_PX, self.height - FONT_CELL_PX - 2, scale=1)
        self.graphics.update()

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
        text = "{:02}:{:02}".format(hour, minute)
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

        self.graphics.update()

    def show_message(self, text):
        """Small utility view for boot/status messages (e.g. 'Syncing time...')."""
        self._clear()
        self.graphics.text(text, MARGIN_PX, self.height // 2 - 4, scale=1)
        self.graphics.update()
