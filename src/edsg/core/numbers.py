"""Formatting numbers so a person can read them.

Elite deals in quantities that span a wide range — a criterion might be
capped at fifty tonnes or at a billion credits — and Python's ``%g`` and
``repr`` reach for scientific notation well inside that range. A unit cap
of a million rendered as ``1e+06``, which is not a number anybody wants
to read in a squadron report.

Two shapes are offered:

:func:`plain` gives the number in full, with thousands separators, and is
the default anywhere the exact figure matters — a payout, a cap, a
points total.

:func:`compact` abbreviates to three significant figures with a unit
suffix, giving ``1.25M``, ``7B``, ``3.2K``. Use it only where space is
genuinely short and the reader wants the magnitude rather than the
figure, such as a progress bar caption.

Neither ever produces an exponent.
"""

from __future__ import annotations

from math import isfinite, isnan

#: Suffixes, largest first. Trillions are reachable: a fleet carrier
#: trading event can put a squadron's combined turnover past 10^12.
_SUFFIXES: tuple[tuple[float, str], ...] = (
    (1_000_000_000_000.0, "T"),
    (1_000_000_000.0, "B"),
    (1_000_000.0, "M"),
    (1_000.0, "K"),
)


def plain(value: float, decimals: int | None = None) -> str:
    """Return the number in full, with thousands separators.

    ``decimals`` of ``None`` shows a whole number when the value is whole
    and two places when it is not, which suits points totals that are
    usually integers but need not be.
    """
    if not isfinite(value):
        return "—"
    if decimals is not None:
        return f"{value:,.{decimals}f}"
    if abs(value - round(value)) < 1e-9:
        return f"{round(value):,}"
    return f"{value:,.2f}"


def compact(value: float, places: int = 2) -> str:
    """Return a short, readable form: ``1.25M``, ``7B``, ``3.2K``.

    Trailing zeros are dropped, so a round number reads as ``7B`` rather
    than ``7.00B``. Anything under a thousand is shown in full, because
    abbreviating it would only lose precision.
    """
    if not isfinite(value):
        return "—"
    if isnan(value):
        return "—"

    sign = "-" if value < 0 else ""
    size = abs(value)

    for threshold, suffix in _SUFFIXES:
        if size >= threshold:
            scaled = size / threshold
            # Keep three significant figures: 1.25M, 12.5M, 125M.
            if scaled >= 100:
                text = f"{scaled:.0f}"
            elif scaled >= 10:
                text = f"{scaled:.{max(0, places - 1)}f}"
            else:
                text = f"{scaled:.{places}f}"
            if "." in text:
                text = text.rstrip("0").rstrip(".")
            return f"{sign}{text}{suffix}"

    return plain(value)


def credits(value: float, unit: str = "Cr", short: bool = False) -> str:
    """Return a credit amount, in full or abbreviated."""
    figure = compact(value) if short else plain(value, 0)
    return f"{figure} {unit}".strip()


def quantity(value: float) -> str:
    """Return a unit count with no trailing ``.0`` and no exponent.

    Used wherever a criterion's cap, minimum or points-per-unit is shown.
    These were the values reaching users as ``1e+06``.
    """
    return plain(value)


def percentage(value: float, places: int = 1) -> str:
    """Return a fraction as a percentage, without a pointless ``.0``."""
    if not isfinite(value):
        return "—"
    text = f"{value * 100:.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}%"


__all__ = ["compact", "credits", "percentage", "plain", "quantity"]
