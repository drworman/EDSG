"""ED: Squad Goals (EDSG).

A cross-platform desktop application for running competitive events in
Elite Dangerous. Organizers define an event and distribute a signed
invitation; participants generate a signed submission from their own
journal files; organizers close the event and produce standings.
"""

from __future__ import annotations

from edsg.version import __version__, version_date, version_tuple

__all__ = ["__version__", "version_date", "version_tuple"]
