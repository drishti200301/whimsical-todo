"""
popup.py
--------
The "magic" popup: a custom-drawn window (no OS title bar) with a
constant 220x280 outer frame. As soon as it opens, it shows the flower
scene for your nearest task deadline with a live countdown underneath.

Key Qt concepts introduced here:

* Qt.FramelessWindowHint -- tells the OS "don't draw your normal title
  bar/border for this window; I'll draw my own."  That's what lets us
  use popup-panel.png / popup-titlebar.png as the visible frame instead
  of the operating system's default one.
* QTimer -- fires a function repeatedly on an interval. Here it ticks
  once a second to update the countdown text.
* Signals/slots -- Qt's way of letting one piece of code say "something
  happened" (a *signal*) without needing to know who, if anyone, is
  listening. Other code "connects" a function (a *slot*) to react to
  it. We use this so popup.py doesn't need to know anything about your
  task list -- main.py hands it a callback instead.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QPainter, QFont, QTransform
from PySide6.QtWidgets import QWidget, QPushButton, QLabel

# The frame the whole popup design was built around.
FRAME_WIDTH = 220
FRAME_HEIGHT = 280
TITLEBAR_HEIGHT = 30
CONTENT_HEIGHT = FRAME_HEIGHT - TITLEBAR_HEIGHT  # 250

# The flower scenes are 220x220 -- drawn flush at the top of the content
# area. Whatever vertical space is left in the frame below that (250 -
# 220 = 30px) is reserved for the countdown text, so the numbers sit
# below the picture instead of overlapping it.
FLOWER_SIZE = 220
TIME_LABEL_HEIGHT = CONTENT_HEIGHT - FLOWER_SIZE  # 30


def _load_pixmap(assets_dir: Path, filename: str) -> QPixmap:
    path = assets_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return QPixmap(str(path))


class _ClickableImageButton(QPushButton):
    """A QPushButton that shows a PNG with no border/background around it,
    so it looks like a hand-drawn image rather than a native OS button."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setIcon(pixmap)
        self.setIconSize(pixmap.size())
        self.setFixedSize(pixmap.size())
        # Strip away the native button chrome (border, background, focus
        # rectangle) so only the icon is visible.
        self.setStyleSheet(
            "QPushButton { border: none; background: transparent; }"
        )
        self.setCursor(Qt.PointingHandCursor)


class MagicPopup(QWidget):
    """The frameless popup window itself."""

    # Emitted as soon as the popup opens and the countdown starts --
    # main.py uses this to know when it should start spawning periodic
    # creature reminders.
    countdown_started = Signal()
    # Emitted when the popup window closes -- main.py uses this to stop
    # spawning creature reminders once the popup is gone.
    popup_closed = Signal()

    def __init__(self, assets_dir: Path, get_active_task, parent=None):
        """
        get_active_task: a zero-argument function (a *callback*) that
        main.py gives us. Calling it returns (task, task_index) for the
        soonest-due unfinished task, or (None, None) if there isn't one.
        Popup.py doesn't need to know anything about how tasks are
        stored -- main.py owns that, and just hands us a way to ask.
        """
        super().__init__(parent)
        self.assets_dir = Path(assets_dir)
        self.get_active_task = get_active_task

        # --- Load assets ---
        raw_panel = _load_pixmap(self.assets_dir, "popup-panel.png")
        # NOTE: popup-panel.png arrived as 280x220 (landscape), but every
        # other asset in this design (the 220-wide titlebar, the 220x220
        # flower scenes) assumes a 220-wide x 280-tall *portrait* frame.
        # Rather than guess at a totally different layout, we rotate the
        # panel image 90 degrees here so it matches the frame everything
        # else was designed for. If you'd rather keep it un-rotated,
        # delete this transform and adjust FRAME_WIDTH/FRAME_HEIGHT above.
        if raw_panel.width() != FRAME_WIDTH or raw_panel.height() != FRAME_HEIGHT:
            raw_panel = raw_panel.transformed(QTransform().rotate(90))
        self.panel_pix = raw_panel

        self.titlebar_pix = _load_pixmap(self.assets_dir, "popup-titlebar.png")
        self.close_pix = _load_pixmap(self.assets_dir, "popup-close.png")
        # NOTE: the provided file is named "popup-minimise.png" (British
        # spelling), not "popup-minimize.png" as in the original asset
        # list -- using the actual filename here.
        self.minimize_pix = _load_pixmap(self.assets_dir, "popup-minimise.png")
        self.flower_pixmaps = [
            _load_pixmap(self.assets_dir, f"flower-scene-{i}.png") for i in range(1, 5)
        ]
        # NOTE: the "Start" screen (start-button.png) and the yellow
        # digit-background.png plaque behind the numbers have both been
        # removed per your last update -- the popup now jumps straight
        # to the countdown, and the time is drawn directly below the
        # flower scene instead of on top of a plaque.

        # --- Frameless, fixed-size window ---
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setFixedSize(FRAME_WIDTH, FRAME_HEIGHT)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._build_ui()

        # Dragging state: since there's no OS title bar, we implement
        # "click and drag the titlebar to move the window" ourselves.
        self._drag_offset = None

        # Countdown ticks once a second, for as long as the popup is open.
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._update_countdown)

        # Start the countdown immediately -- there's no more separate
        # "Start" screen to click through first. We use a zero-delay
        # QTimer instead of calling _start_countdown() directly here:
        # main.py hasn't had a chance to connect to countdown_started
        # yet at this exact point (it can only do that *after* this
        # constructor returns), so emitting the signal right now would
        # mean nobody's listening and the creature-reminder scheduler
        # in main.py would never start. A `QTimer.singleShot(0, ...)`
        # defers the call until right after the constructor finishes
        # and control returns to the caller -- by then, main.py has
        # connected its listener.
        QTimer.singleShot(0, self._start_countdown)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        # The time label sits in the strip directly below the flower
        # scene (see TIME_LABEL_HEIGHT above), not on top of the artwork.
        self.time_label = QLabel(self)
        self.time_label.setAlignment(Qt.AlignCenter)
        # Smaller than before (was 20pt over a wide plaque) since it now
        # has to fit in a slim 30px-tall strip under the picture.
        self.time_label.setFont(QFont("Arial", 13, QFont.Bold))
        self.time_label.setStyleSheet("color: #3a2a1a;")  # readable on the tan panel
        self.time_label.setGeometry(
            0, TITLEBAR_HEIGHT + FLOWER_SIZE, FRAME_WIDTH, TIME_LABEL_HEIGHT
        )

        # Close/minimize buttons sit on top of the titlebar strip.
        self.close_button = _ClickableImageButton(self.close_pix, self)
        self.close_button.clicked.connect(self.close)
        self.minimize_button = _ClickableImageButton(self.minimize_pix, self)
        self.minimize_button.clicked.connect(self.showMinimized)
        self._position_titlebar_buttons()

    def _position_titlebar_buttons(self):
        margin = 4
        y = (TITLEBAR_HEIGHT - self.close_pix.height()) // 2
        self.close_button.move(FRAME_WIDTH - self.close_pix.width() - margin, y)
        self.minimize_button.move(
            FRAME_WIDTH - self.close_pix.width() - self.minimize_pix.width() - margin * 2, y
        )

    # ------------------------------------------------------------------
    # Painting the constant frame (panel + titlebar + flower scene)
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. The constant outer panel, always drawn first (bottom layer).
        painter.drawPixmap(0, 0, self.panel_pix)

        # 2. The flower scene, flush against the top of the content area
        # (directly under the titlebar).
        flower = self.flower_pixmaps[self._active_flower_index()]
        painter.drawPixmap(0, TITLEBAR_HEIGHT, flower)

        # 3. Title bar strip across the top, drawn last so it's always
        # on top of the flower scene at the seam between the two.
        painter.drawPixmap(0, 0, self.titlebar_pix)

    def _active_flower_index(self) -> int:
        _, index = self.get_active_task()
        index = index or 0
        return index % 4  # cycle through the 4 flower scenes, as requested

    # ------------------------------------------------------------------
    # Countdown behavior
    # ------------------------------------------------------------------
    def _start_countdown(self):
        self._update_countdown()
        self._countdown_timer.start(1000)  # tick every second
        self.update()  # request a repaint so the flower scene appears
        self.countdown_started.emit()

    def _update_countdown(self):
        task, _ = self.get_active_task()
        if task is None:
            self.time_label.setText("No tasks!")
            self._countdown_timer.stop()
            return
        remaining = int(task.seconds_remaining())
        if remaining <= 0:
            self.time_label.setText("Time's up!")
            self._countdown_timer.stop()
            return
        hours, rem = divmod(remaining, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            self.time_label.setText(f"{hours}:{minutes:02d}:{seconds:02d}")
        else:
            self.time_label.setText(f"{minutes:02d}:{seconds:02d}")
        self.update()  # in case the active task (and thus flower scene) changed

    # ------------------------------------------------------------------
    # Manual window dragging (since there's no OS titlebar to drag by)
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.position().y() <= TITLEBAR_HEIGHT:
            self._drag_offset = event.position().toPoint()
        else:
            self._drag_offset = None

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None:
            new_pos = self.mapToGlobal(event.position().toPoint() - self._drag_offset)
            self.move(new_pos)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None

    def closeEvent(self, event):
        self._countdown_timer.stop()
        self.popup_closed.emit()
        super().closeEvent(event)
