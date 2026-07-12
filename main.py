"""
main.py
-------
Entry point and main to-do list window.

Run this file to start the app:

    python main.py

Key Qt concepts introduced here:

* QMainWindow / QWidget -- QWidget is the base class for basically
  anything visible in Qt. QMainWindow adds optional extras (menu bar,
  status bar) we don't need, so we just use a plain QWidget as our
  top-level window.
* Layouts (QVBoxLayout, QHBoxLayout) -- rather than giving every widget
  a fixed x/y position, you place widgets into a *layout*, and Qt
  automatically arranges and resizes them for you. QVBoxLayout stacks
  things vertically, QHBoxLayout stacks things horizontally, and you
  can nest them.
* Signals/slots (again) -- e.g. `button.clicked.connect(some_function)`
  means "when this button is clicked, call some_function". This is how
  nearly all interactivity in Qt works.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTime, QTimer
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTimeEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
)

from tasks import Task
from popup import MagicPopup
from creature import CreatureWindow

ASSETS_DIR = Path(__file__).parent / "assets"

# The cursive/script font used for the "handwritten" style text overlays
# (the title on the header banner, and "MAGIC" on the magic button).
# "Monotype Corsiva" ships with Microsoft Office/Windows, so it's very
# likely already on your machine. If it isn't installed, Qt silently
# falls back to a default font instead of erroring -- everything still
# works, it just won't look as script-y. To use a different font,
# just change this one string.
WHIMSICAL_FONT_FAMILY = "Monotype Corsiva"

# --- Reminder frequency rules ---
# You asked for Miffy to show up at three *guaranteed* checkpoints as a
# deadline approaches -- at 45, 30, and 15 minutes remaining -- no
# matter how long the task's original countdown was. Once a task has
# more than an hour left, there's nothing to check against yet, so we
# fall back to a plain periodic ping (every 30 minutes -- the low end
# of the "30 to 45 min" range you gave) until it enters that 45-minute
# window, at which point the guaranteed checkpoints take over.
CHECKPOINT_MINUTES = (45, 30, 15)
FAR_OUT_INTERVAL_MINUTES = 30


class HeaderWidget(QWidget):
    """The banner across the top of the main window: the header-banner.png
    image (clouds) with a bold, cursive title painted on top of it.

    We use a plain QWidget + paintEvent here (rather than a QLabel with a
    stylesheet) because QLabel styling can't easily draw text *centered on
    top of* a background image with a custom font -- doing it with
    QPainter gives us full control over exactly where the text sits.
    """

    def __init__(self, banner_pix: QPixmap, title: str, parent=None):
        super().__init__(parent)
        self.banner_pix = banner_pix
        self.title = title
        self.setFixedSize(banner_pix.size())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, self.banner_pix)

        font = QFont(WHIMSICAL_FONT_FAMILY, 28, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#3a2a1a"))  # warm dark brown, readable on sky-blue
        painter.drawText(self.rect(), Qt.AlignCenter, self.title)


class _MagicButton(QPushButton):
    """The 'magic' button: paints magic-button.png as its background and
    draws bold cursive "MAGIC" text centered on top of it. We draw both
    ourselves (rather than using setIcon + setText) so the text sits
    exactly centered over the artwork instead of next to it."""

    def __init__(self, pixmap: QPixmap, text: str, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap
        self.text_label = text
        self.setFixedSize(pixmap.size())
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, self.pixmap)

        font = QFont(WHIMSICAL_FONT_FAMILY, 16, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor("#3a2a1a"))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text_label)


class _ImageButton(QPushButton):
    """Same idea as popup.py's image button: a QPushButton that displays
    a PNG with no visible native button chrome around it."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setIcon(pixmap)
        self.setIconSize(pixmap.size())
        self.setFixedSize(pixmap.size())
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")
        self.setCursor(Qt.PointingHandCursor)


class TaskRowWidget(QWidget):
    """One row in the task list: a checkbox image, the task name +
    deadline, and a delete icon. We build this as its own small QWidget
    so QListWidget can use one per row via setItemWidget()."""

    def __init__(self, task: Task, on_toggle, on_delete, parent=None):
        super().__init__(parent)
        self.task = task

        self.checkbox_empty = QPixmap(str(ASSETS_DIR / "checkbox-empty.png"))
        self.checkbox_checked = QPixmap(str(ASSETS_DIR / "checkbox-checked.png"))
        delete_pix = QPixmap(str(ASSETS_DIR / "delete-icon.png"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.checkbox_button = _ImageButton(
            self.checkbox_checked if task.done else self.checkbox_empty
        )
        self.checkbox_button.clicked.connect(lambda: on_toggle(self))
        layout.addWidget(self.checkbox_button)

        text = f"{task.name}  —  {task.deadline.strftime('%I:%M %p').lstrip('0')}"
        self.label = QLabel(text)
        layout.addWidget(self.label, stretch=1)

        self.delete_button = _ImageButton(delete_pix)
        self.delete_button.clicked.connect(lambda: on_delete(self))
        layout.addWidget(self.delete_button)

        self._apply_done_style()

    def refresh_checkbox(self):
        self.checkbox_button.setIcon(
            self.checkbox_checked if self.task.done else self.checkbox_empty
        )
        self._apply_done_style()

    def _apply_done_style(self):
        # NOTE: Qt's stylesheets (QSS) don't actually support the CSS
        # "text-decoration" property on QLabel -- it's silently ignored,
        # which is why a strikethrough never showed up before. A real
        # strikethrough has to be set on the QFont itself instead.
        font = self.label.font()
        font.setPointSize(14)
        font.setStrikeOut(self.task.done)
        self.label.setFont(font)
        self.label.setStyleSheet("color: gray;" if self.task.done else "")


class TodoWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whimsical To-Do")
        self.setFixedSize(600, 500)

        self.main_bg_pix = QPixmap(str(ASSETS_DIR / "main-background.png"))
        self.header_pix = QPixmap(str(ASSETS_DIR / "header-banner.png"))
        magic_button_pix = QPixmap(str(ASSETS_DIR / "magic-button.png"))

        # Tasks are stored in the order they were added, which is also
        # the order used for "task index modulo 4" -> flower scene.
        self.tasks: list[Task] = []
        self.popup: MagicPopup | None = None
        self.active_creature: CreatureWindow | None = None

        self._build_ui(magic_button_pix)

        # Reminder scheduler: only running while a popup's countdown is
        # active (see _on_countdown_started / _on_popup_closed below).
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._maybe_show_creature)
        # Which checkpoints (see CHECKPOINT_MINUTES) haven't fired yet
        # for the *current* active task, and when the next "far out"
        # periodic ping is due if that task has over an hour left.
        # Reset whenever a new countdown starts or the active task
        # changes (e.g. the previous one got checked off).
        self._checkpoints_remaining = set()
        self._next_periodic_reminder_at = None
        self._reminder_active_task_id = None

    # ------------------------------------------------------------------
    def _build_ui(self, magic_button_pix: QPixmap):
        # We paint main_bg_pix as a background in paintEvent (below)
        # rather than via QSS/stylesheet, so we get pixel-exact control
        # and it works identically on Windows and macOS.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = HeaderWidget(self.header_pix, "Your Whimsical Todo List")
        layout.addWidget(header, alignment=Qt.AlignHCenter)

        # --- Add-task row ---
        add_row = QHBoxLayout()
        add_row.setContentsMargins(16, 12, 16, 4)
        add_row.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Task name…")
        # Capped width (rather than letting it stretch to fill all
        # available space) so the time picker and Add button next to it
        # always have enough room to show fully instead of getting
        # squeezed/clipped.
        self.name_input.setMaximumWidth(260)
        self.name_input.setMinimumHeight(30)

        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("hh:mm AP")
        self.time_input.setTime(QTime.currentTime())
        # Wide/tall enough to always show "hh:mm AM/PM" plus the little
        # up/down arrows in full, instead of them being cropped.
        self.time_input.setMinimumWidth(120)
        self.time_input.setMinimumHeight(30)

        add_button = QPushButton("Add")
        add_button.setMinimumHeight(30)
        add_button.clicked.connect(self._on_add_task)

        add_row.addWidget(self.name_input, stretch=1)
        add_row.addWidget(self.time_input)
        add_row.addWidget(add_button)
        layout.addLayout(add_row)

        # --- Task list ---
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("QListWidget { background: transparent; border: none; }")
        layout.addWidget(self.list_widget, stretch=1)

        # --- Magic button ---
        magic_row = QHBoxLayout()
        magic_row.setContentsMargins(16, 4, 16, 12)
        magic_row.addStretch()
        self.magic_button = _MagicButton(magic_button_pix, "MAGIC")
        self.magic_button.clicked.connect(self._open_popup)
        magic_row.addWidget(self.magic_button)
        magic_row.addStretch()
        layout.addLayout(magic_row)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.main_bg_pix)
        super().paintEvent(event)

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------
    def _on_add_task(self):
        name = self.name_input.text().strip()
        if not name:
            return
        task = Task.from_time_of_day(name, self.time_input.time().toPython())
        self.tasks.append(task)
        self._add_task_row(task)
        self.name_input.clear()

    def _add_task_row(self, task: Task):
        row_widget = TaskRowWidget(task, self._on_toggle_task, self._on_delete_task)
        item = QListWidgetItem(self.list_widget)
        item.setSizeHint(row_widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, row_widget)

    def _on_toggle_task(self, row_widget: TaskRowWidget):
        row_widget.task.done = not row_widget.task.done
        row_widget.refresh_checkbox()

    def _on_delete_task(self, row_widget: TaskRowWidget):
        self.tasks.remove(row_widget.task)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if self.list_widget.itemWidget(item) is row_widget:
                self.list_widget.takeItem(i)
                break

    def get_active_task(self):
        """Returns (task, index) for the not-done task with the soonest
        deadline, or (None, None) if there are no pending tasks.
        `index` is that task's position in self.tasks (used for the
        flower-scene-cycling rule: index % 4)."""
        pending = [(i, t) for i, t in enumerate(self.tasks) if not t.done]
        if not pending:
            return None, None
        i, task = min(pending, key=lambda pair: pair[1].deadline)
        return task, i

    # ------------------------------------------------------------------
    # Popup + creature reminders
    # ------------------------------------------------------------------
    def _open_popup(self):
        self.popup = MagicPopup(ASSETS_DIR, self.get_active_task, parent=None)
        self.popup.countdown_started.connect(self._on_countdown_started)
        self.popup.popup_closed.connect(self._on_popup_closed)
        self.popup.show()

    def _on_countdown_started(self):
        # Fresh reminder state for this popup session.
        self._checkpoints_remaining = set(CHECKPOINT_MINUTES)
        self._next_periodic_reminder_at = None
        self._reminder_active_task_id = None
        self._reminder_timer.start(5000)  # check every 5s whether it's time

    def _on_popup_closed(self):
        self._reminder_timer.stop()
        if self.active_creature is not None:
            self.active_creature.close()
            self.active_creature = None

    def _maybe_show_creature(self):
        task, _ = self.get_active_task()
        if task is None:
            self._reminder_timer.stop()
            return

        # If the active task changed since the last check (e.g. the
        # previous one got marked done and a different one is now
        # nearest), start its checkpoints over from scratch rather than
        # reusing whatever the old task had already used up.
        task_id = id(task)
        if task_id != self._reminder_active_task_id:
            self._reminder_active_task_id = task_id
            self._checkpoints_remaining = set(CHECKPOINT_MINUTES)
            self._next_periodic_reminder_at = None

        minutes_remaining = task.seconds_remaining() / 60
        now = datetime.now()

        if minutes_remaining > 60:
            # Far-out zone: just a plain periodic ping every
            # FAR_OUT_INTERVAL_MINUTES, until the task enters the
            # 60-minutes-or-less window below.
            if self._next_periodic_reminder_at is None:
                self._next_periodic_reminder_at = now + timedelta(
                    minutes=FAR_OUT_INTERVAL_MINUTES
                )
            elif now >= self._next_periodic_reminder_at:
                self._spawn_creature(task)
                self._next_periodic_reminder_at = now + timedelta(
                    minutes=FAR_OUT_INTERVAL_MINUTES
                )
        else:
            # Checkpoint zone: guarantee one ping each time the
            # remaining time drops to/below 45, then 30, then 15
            # minutes -- regardless of how long this task's countdown
            # originally was.
            for checkpoint in sorted(self._checkpoints_remaining, reverse=True):
                if minutes_remaining <= checkpoint:
                    self._spawn_creature(task)
                    self._checkpoints_remaining.discard(checkpoint)
                    break  # only fire one checkpoint per check

    def _spawn_creature(self, task: Task):
        if self.active_creature is None:
            minutes_left = max(0, int(task.seconds_remaining() // 60))
            self.active_creature = CreatureWindow(ASSETS_DIR, minutes_left)
            self.active_creature.dismissed.connect(self._on_creature_dismissed)

    def _on_creature_dismissed(self):
        self.active_creature = None


def main():
    app = QApplication(sys.argv)
    window = TodoWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
