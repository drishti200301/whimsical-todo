"""
tasks.py
--------
A plain Python data class describing one to-do item.

We keep this separate from any Qt/UI code on purpose: the *data* your
app works with (a task's name, deadline, and completed state) doesn't
need to know anything about windows or buttons. This separation makes
the code much easier to read and test as it grows.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, time as dt_time


@dataclass
class Task:
    """One to-do item.

    `@dataclass` is a decorator (a function that wraps another piece of
    code to add behavior) that automatically writes the boilerplate
    __init__ method for a simple class like this, based on the type
    hints below. Without it, you'd have to write:

        def __init__(self, name, deadline, done=False):
            self.name = name
            self.deadline = deadline
            self.done = done

    yourself. @dataclass generates that for you.
    """

    name: str
    deadline: datetime
    done: bool = False

    @classmethod
    def from_time_of_day(cls, name: str, deadline_time: dt_time) -> "Task":
        """Build a Task from just a clock time (e.g. 4:00 PM).

        The user only enters a time, not a full date, so we attach
        today's date. If that time has already passed today, we assume
        they mean tomorrow instead (a deadline of "9:00 AM" typed at
        11:00 PM almost certainly means tomorrow morning).
        """
        now = datetime.now()
        candidate = datetime.combine(now.date(), deadline_time)
        if candidate <= now:
            # timedelta(days=1) correctly rolls over month/year boundaries
            # (e.g. Jan 31 -> Feb 1), unlike hand-rolling `.day + 1` would.
            candidate += timedelta(days=1)
        return cls(name=name, deadline=candidate)

    def seconds_remaining(self) -> float:
        """How many seconds are left until this task's deadline (can be negative)."""
        return (self.deadline - datetime.now()).total_seconds()
