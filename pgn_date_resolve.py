"""Resolve PGN [Date] from Date and common alternate tags, and normalize for lila-openingexplorer."""

from __future__ import annotations

__all__ = [
    "has_usable_year",
    "to_date_token",
    "resolve_pgn_date",
    "format_pgn_date_for_header",
    "normalize_masters_date",
]

# Explorer LaxDate: years 1952..=3000, dot-separated.
_YMIN, _YMAX = 1952, 3000

# If [Date] is missing or not usable, try these in order (common in Lichess, TWIC, DGT, etc.)
_FALLBACK_DATE_KEYS: tuple[str, ...] = (
    "EventDate",
    "UTCDate",
    "SourceDate",
    "DateTime",
)


def to_date_token(raw: str) -> str:
    """Take the calendar part from a tag value (strip time, ISO T, first word)."""
    s = (raw or "").strip()
    if not s:
        return s
    if "T" in s:
        s = s.split("T", 1)[0]
    if " " in s:
        s = s.split()[0]
    return s


def has_usable_year(raw: str) -> bool:
    """
    True if the value has a known 4-digit year (no '?' in the year), PGN style or ISO/hyphen.
    """
    s = to_date_token(raw)
    s = s.replace("-", ".").replace("/", ".")
    parts = [p for p in s.split(".") if p]
    if not parts:
        return False
    y = parts[0]
    if "?" in y or len(y) != 4 or not y.isdigit():
        return False
    return True


def _get_header(headers: object, key: str) -> str:
    if headers is None:
        return ""
    v = None
    get = getattr(headers, "get", None)
    if callable(get):
        v = get(key)
    if v is None:
        try:
            v = headers[key]  # type: ignore[index]
        except Exception:  # noqa: BLE001
            v = None
    if v is None:
        return ""
    if not isinstance(v, str):
        v = str(v)
    return v.strip()


def resolve_pgn_date(headers: object) -> str:
    """
    Prefer [Date] when it has a usable year; else first usable among EventDate, UTCDate,
    SourceDate, DateTime. Returns the best raw string (may still be hyphen or ISO form).
    """
    d = _get_header(headers, "Date")
    if has_usable_year(d):
        return d
    for key in _FALLBACK_DATE_KEYS:
        v = _get_header(headers, key)
        if has_usable_year(v):
            return v
    return d


def format_pgn_date_for_header(resolved: str) -> str:
    """
    Value suitable for a new [Date "…"] line: dot-separated, no time part.
    Preserves real years (e.g. 1920) for the file; use normalize_masters_date for import payload.
    """
    s = to_date_token(resolved)
    s = s.replace("-", ".").replace("/", ".")
    if has_usable_year(s):
        return s
    return f"{_YMIN}.01.01"


def normalize_masters_date(raw) -> str:
    """lila-openingexplorer: dot-separated, year in 1952..=3000."""
    s = to_date_token((raw or "").strip() if raw is not None else "")
    s = s.replace("-", ".").replace("/", ".")
    if not s:
        return f"{_YMIN}.01.01"
    parts = [p for p in s.split(".") if p]
    if not parts:
        return f"{_YMIN}.01.01"
    y_raw = parts[0]
    if y_raw and all(c == "?" for c in y_raw):
        y = _YMIN
    else:
        try:
            y = int(y_raw)
        except ValueError:
            y = _YMIN
    y = max(_YMIN, min(_YMAX, y))
    if len(parts) == 1:
        return str(y)
    return str(y) + "." + ".".join(parts[1:])
