"""Entry point for the organizer binary.

Launches the graphical interface by default. Passing ``--cli`` hands off
to the headless interface, which is how the release workflow smoke-tests
a built binary on a machine with no display.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the organizer application, or the headless interface."""
    # Declared before anything reads configuration, so every later
    # lookup lands in this binary's own directory.
    from edsg.core.paths import ROLE_ORGANIZER, set_role

    set_role(ROLE_ORGANIZER)

    argv = sys.argv[1:]
    if argv and argv[0] == "--cli":
        # These binaries are built windowed, so on Windows they start
        # with no usable stdout. Reconnect it before anything tries to
        # print, or the command runs and its output goes nowhere.
        from edsg.win_console import enable_console_output

        enable_console_output()

        from edsg.cli import main as run_cli

        return run_cli(argv[1:])

    from edsg.gui.organizer import main as run_gui

    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
