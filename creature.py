"""
creature.py
-----------
The little roaming creature that pops up on top of every other app to
remind you how much time is left.

Key Qt concepts introduced here:

* QWidget with special *window flags* -- flags are just bit settings you
  pass in that tell the OS "don't draw a title bar for this window",
  "keep it on top of everything else", etc.
* Qt.WA_TranslucentBackground -- an *attribute* (a different mechanism
  from flags, but same idea: a switch you flip on a widget) that lets
  a window have a see-through background instead of a solid rectangle.
* QTimer -- fires a function repeatedly after a set interval. We use one
  timer to animate the drift movement (~60 times a second) and it is
  completely separate from the *scheduling* timer in main.py that
  decides *when* a creature should appear at all.
* QPainter -- Qt's drawing API. paintEvent() is a method Qt calls
  automatically whenever the widget needs to redraw itself; inside it
  we use a QPainter to draw our PNG images and text onto the widget.
"""

import math
import random

from PySide6.QtCore import Qt, QTimer, QRect, Signal
from PySide6.QtGui import QPixmap, QPainter, QFont
from PySide6.QtWidgets import QWidget, QApplication


class CreatureWindow(QWidget):
    """A frameless, transparent, always-on-top widget that drifts around
    the screen showing a speech bubble with time remaining, until the
    user clicks it (or a timeout elapses).
    """

    dismissed = Signal()  # a custom Qt signal we emit when the creature closes

    def __init__(self, assets_dir, minutes_left: int, lifetime_ms: int = 20_000):
        super().__init__()

        self.creature_pix = QPixmap(str(assets_dir / "creature-idle.png"))
        self.bubble_pix = QPixmap(str(assets_dir / "speech-bubble.png"))
        self.minutes_left = minutes_left

        # --- Window flags: this combination is what makes the creature
        # behave like a "desktop pet" instead of a normal window. ---
        self.setWindowFlags(
            Qt.FramelessWindowHint       # no title bar / border
            | Qt.WindowStaysOnTopHint    # always above other windows
            | Qt.Tool                    # don't show a taskbar/dock icon
        )
        # Makes the parts of the widget we don't paint on fully see-through,
        # instead of the usual opaque grey background.
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Widget size = creature image plus room for the speech bubble
        # above it.
        width = max(self.creature_pix.width(), self.bubble_pix.width())
        height = self.creature_pix.height() + self.bubble_pix.height()
        self.resize(width, height)

        # --- Pick a random starting position and drift target on screen ---
        screen_geo = QApplication.primaryScreen().availableGeometry()
        margin = 40
        self._x = random.uniform(margin, screen_geo.width() - width - margin)
        self._y = random.uniform(margin, screen_geo.height() - height - margin)
        self.move(int(self._x), int(self._y))

        # Smooth drift is done with simple sine waves offset by a random
        # phase, rather than choosing new random destinations and easing
        # toward them. It's a cheap way to get "gentle floating" motion
        # without needing a physics/animation library.
        self._t = 0.0
        self._phase_x = random.uniform(0, math.tau)
        self._phase_y = random.uniform(0, math.tau)
        self._speed = random.uniform(0.6, 1.0)
        self._amplitude = random.uniform(25, 60)
        self._origin_x = self._x
        self._origin_y = self._y

        self._drift_timer = QTimer(self)
        self._drift_timer.timeout.connect(self._advance_drift)
        self._drift_timer.start(16)  # ~60 frames per second

        # Auto-dismiss after `lifetime_ms` even if never clicked, so a
        # missed reminder doesn't sit on screen forever.
        self._lifetime_timer = QTimer(self)
        self._lifetime_timer.setSingleShot(True)
        self._lifetime_timer.timeout.connect(self.close)
        self._lifetime_timer.start(lifetime_ms)

        self.show()

    def _advance_drift(self):
        """Called ~60x/sec by _drift_timer to nudge the creature's position."""
        self._t += 0.016 * self._speed
        dx = math.sin(self._t) * self._amplitude
        dy = math.cos(self._t * 0.7) * (self._amplitude * 0.6)
        self.move(int(self._origin_x + dx), int(self._origin_y + dy))

    def paintEvent(self, event):
        """Qt calls this automatically whenever the widget needs (re)drawing."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Speech bubble on top, creature below it.
        bubble_x = (self.width() - self.bubble_pix.width()) // 2
        painter.drawPixmap(bubble_x, 0, self.bubble_pix)

        creature_x = (self.width() - self.creature_pix.width()) // 2
        painter.drawPixmap(creature_x, self.bubble_pix.height(), self.creature_pix)

        # Draw "N min" text centered on top of the speech bubble.
        painter.setFont(QFont("Arial", 13, QFont.Bold))
        painter.setPen(Qt.black)
        text_rect = QRect(bubble_x, 0, self.bubble_pix.width(), self.bubble_pix.height())
        painter.drawText(text_rect, Qt.AlignCenter, f"{self.minutes_left} min")

    def mousePressEvent(self, event):
        """Qt calls this when the user clicks anywhere on the widget.
        We treat any click as "dismiss the creature"."""
        self._drift_timer.stop()
        self._lifetime_timer.stop()
        self.dismissed.emit()
        self.close()
