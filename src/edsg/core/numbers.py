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
    if abs(value - round(value)) < 1e-12:
        return f"{round(value):,}"

    # Enough places to hold anything a criterion is likely to carry, then
    # trimmed. Rounding to two would silently destroy a points-per-unit
    # of 0.001, which is a perfectly reasonable thing to set.
    text = f"{value:,.10f}".rstrip("0").rstrip(".")
    return text or "0"


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


#: Multipliers accepted when reading a number back from a field, so a
#: value shown as ``250K`` can be typed straight back in.
_MULTIPLIERS = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0, "t": 1e12}

#: Characters people and locales use to group digits.
_SEPARATORS = ",_' \u00a0\u202f"


def parse(text: str) -> float | None:
    """Read a number back from something a person typed or was shown.

    Accepts the forms this module produces and the ones people reach for
    anyway: ``1,000,000``, ``1 000 000``, ``250K``, ``4.3k``, ``1B``.
    Returns ``None`` for anything empty, and raises :class:`ValueError`
    for text that is not a number at all.

    This exists because a field displaying ``1,000,000`` has to be
    readable *and* editable. Showing a grouped number that the parser
    then rejects is worse than showing no grouping at all.
    """
    cleaned = text.strip()
    if not cleaned:
        return None

    for character in _SEPARATORS:
        cleaned = cleaned.replace(character, "")
    if not cleaned:
        raise ValueError(f"'{text}' is not a number.")

    multiplier = 1.0
    suffix = cleaned[-1].lower()
    if suffix in _MULTIPLIERS:
        multiplier = _MULTIPLIERS[suffix]
        cleaned = cleaned[:-1]
        # A bare suffix such as "M" means nothing on its own.
        if not cleaned or cleaned in "+-":
            raise ValueError(f"'{text}' is not a number.")

    try:
        return float(cleaned) * multiplier
    except ValueError as exc:
        raise ValueError(f"'{text}' is not a number.") from exc


def editable(value: float | None) -> str:
    """Return a value for a field the user can edit and re-save.

    Prefers the short form — ``250K``, ``1B`` — because that is what is
    pleasant to read. Falls back to the grouped figure whenever the short
    form would not read back as the same number, so opening a criterion
    and saving it again can never quietly round the value that was set.
    """
    if value is None:
        return ""
    short = compact(value)
    try:
        if parse(short) == value:
            return short
    except ValueError:
        pass
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


__all__ = [
    "compact",
    "credits",
    "editable",
    "parse",
    "percentage",
    "plain",
    "quantity",
]
