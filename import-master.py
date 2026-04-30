#!/usr/bin/env python3

import argparse
import base64
import chess
import chess.pgn
import hashlib
import json
import requests
import sys
import time
from datetime import datetime, timezone

from pgn_date_resolve import has_usable_year, normalize_masters_date, resolve_pgn_date

DATE_FAILS_PGN = "date_fails.pgn"
RESULT_FAILS_PGN = "result_fails.pgn"
HEADER_FAILS_PGN = "header_fails.pgn"
RATING_FAILS_PGN = "rating_fails.pgn"
# Optional 5th CLI path (backward compatible; ignored).
REQUEST_FAILS_PGN = "request_fails.pgn"

IMPORT_MASTERS_URL = "http://localhost:9002/import/masters"
CONNECT_TIMEOUT_SEC = 10
READ_TIMEOUT_SEC = 120
# Per-game PUT attempts (transport errors + HTTP 429/5xx each consume one attempt). Then exit.
MAX_PUT_ATTEMPTS = 50
# Exponential backoff between retries; cap sleep to avoid extreme stalls.
RETRY_BACKOFF_BASE_SEC = 2.0
RETRY_BACKOFF_MAX_SEC = 60.0


def _retry_wait(attempt: int) -> float:
    return min(
        RETRY_BACKOFF_MAX_SEC,
        RETRY_BACKOFF_BASE_SEC * (2 ** min(attempt - 1, 5)),
    )


def put_masters_until_ok(session: requests.Session, obj: dict) -> str:
    """PUT one game with capped retries on transport errors and retryable HTTP status."""
    for attempt in range(1, MAX_PUT_ATTEMPTS + 1):
        try:
            res = session.put(
                IMPORT_MASTERS_URL,
                json=obj,
                timeout=(CONNECT_TIMEOUT_SEC, READ_TIMEOUT_SEC),
            )
        except requests.exceptions.RequestException as err:
            if attempt >= MAX_PUT_ATTEMPTS:
                raise SystemExit(
                    f"gave up on {obj['id']} after {MAX_PUT_ATTEMPTS} attempts (last error: {err})"
                )
            wait = _retry_wait(attempt)
            print(
                f"request error for {obj['id']} (attempt {attempt}/{MAX_PUT_ATTEMPTS}): {err}; "
                f"retry in {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue

        if res.status_code == 200:
            return "ok"

        # Rerun imports: server returns 400 DuplicateGame — treat as success (already stored).
        if res.status_code == 400 and "duplicate game" in res.text.lower():
            return "ok"

        if res.status_code == 400 and "rejected import of" in res.text.lower():
            if "average rating" in res.text.lower():
                return "rating_rejected"
            if "due to date" in res.text.lower():
                return "date_rejected"

        if res.status_code in (429, 502, 503, 504):
            if attempt >= MAX_PUT_ATTEMPTS:
                raise SystemExit(
                    f"gave up on {obj['id']} after {MAX_PUT_ATTEMPTS} attempts "
                    f"(last HTTP {res.status_code}): {res.text[:500]}"
                )
            wait = _retry_wait(attempt)
            print(
                f"HTTP {res.status_code} for {obj['id']} (attempt {attempt}/{MAX_PUT_ATTEMPTS}); "
                f"retry in {wait:.1f}s: {res.text[:500]}",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue

        # Non-retryable HTTP response: surface and stop (bad payload or server bug).
        print(res.text, file=sys.stderr)
        raise SystemExit(f"import failed for {obj['id']}: HTTP {res.status_code}")


def main(
    pgn,
    date_fails_path: str = DATE_FAILS_PGN,
    result_fails_path: str = RESULT_FAILS_PGN,
    header_fails_path: str = HEADER_FAILS_PGN,
    rating_fails_path: str = RATING_FAILS_PGN,
    request_fails_path: str = REQUEST_FAILS_PGN,
    last_id: str | None = None,
):
    _ = request_fails_path  # backward compatibility for optional 5th CLI arg
    session = requests.session()
    date_fails_f = None
    result_fails_f = None
    header_fails_f = None
    rating_fails_f = None
    run_header_written = set()

    last_id_key = last_id.strip() if last_id else None
    seek_last = bool(last_id_key)
    seen_last = False

    while True:
        game = chess.pgn.read_game(pgn)
        if game is None:
            break

        resolved = resolve_pgn_date(game.headers)
        if not has_usable_year(resolved):
            if date_fails_f is None:
                date_fails_f = open(date_fails_path, "a", encoding="utf-8")
            if "date" not in run_header_written:
                date_fails_f.write(f"# run started {run_timestamp()}\n\n")
                run_header_written.add("date")
            print(game, file=date_fails_f, end="")
            date_fails_f.write("\n\n")
            continue

        winner_value = winner(game)
        if winner_value is INVALID_RESULT:
            if result_fails_f is None:
                result_fails_f = open(result_fails_path, "a", encoding="utf-8")
            if "result" not in run_header_written:
                result_fails_f.write(f"# run started {run_timestamp()}\n\n")
                run_header_written.add("result")
            print(game, file=result_fails_f, end="")
            result_fails_f.write("\n\n")
            continue

        try:
            obj = {
                "event": game.headers["Event"],
                "site": game.headers["Site"],
                "date": normalize_masters_date(resolved),
                "round": game.headers["Round"],
                "white": {
                    "name": game.headers["White"],
                    "rating": int(game.headers["WhiteElo"]),
                },
                "black": {
                    "name": game.headers["Black"],
                    "rating": int(game.headers["BlackElo"]),
                },
                "winner": winner_value,
                "moves": " ".join(m.uci() for m in game.end().board().move_stack)
            }
        except (KeyError, ValueError) as err:
            if header_fails_f is None:
                header_fails_f = open(header_fails_path, "a", encoding="utf-8")
            if "header" not in run_header_written:
                header_fails_f.write(f"# run started {run_timestamp()}\n\n")
                run_header_written.add("header")
            print(f"# header parse error: {err}", file=header_fails_f)
            print(game, file=header_fails_f, end="")
            header_fails_f.write("\n\n")
            continue

        obj["id"] = game.headers.get("LichessId") or deterministic_id(obj)

        if seek_last and not seen_last:
            if obj["id"] != last_id_key:
                continue
            seen_last = True
            continue

        import_result = put_masters_until_ok(session, obj)
        if import_result == "rating_rejected":
            if rating_fails_f is None:
                rating_fails_f = open(rating_fails_path, "a", encoding="utf-8")
            if "rating" not in run_header_written:
                rating_fails_f.write(f"# run started {run_timestamp()}\n\n")
                run_header_written.add("rating")
            print(f"# rejected import id: {obj['id']} (average rating policy)", file=rating_fails_f)
            print(game, file=rating_fails_f, end="")
            rating_fails_f.write("\n\n")
            continue
        if import_result == "date_rejected":
            if date_fails_f is None:
                date_fails_f = open(date_fails_path, "a", encoding="utf-8")
            if "date" not in run_header_written:
                date_fails_f.write(f"# run started {run_timestamp()}\n\n")
                run_header_written.add("date")
            print(f"# rejected import id: {obj['id']} (date policy)", file=date_fails_f)
            print(game, file=date_fails_f, end="")
            date_fails_f.write("\n\n")
            continue
        print(obj["id"])

    if seek_last and not seen_last:
        raise SystemExit(
            f"--last-id {last_id_key!r} not found in PGN (no game with this import id)."
        )

    if date_fails_f is not None:
        date_fails_f.close()
    if result_fails_f is not None:
        result_fails_f.close()
    if header_fails_f is not None:
        header_fails_f.close()
    if rating_fails_f is not None:
        rating_fails_f.close()


INVALID_RESULT = object()


def run_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def winner(game):
    result = game.headers.get("Result", "").strip()
    if result == "1-0":
        return "white"
    elif result == "0-1":
        return "black"
    elif result == "1/2-1/2":
        return None
    else:
        return INVALID_RESULT


def deterministic_id(obj):
    digest = hashlib.sha256()
    digest.update(json.dumps(obj, sort_keys=True).encode("utf-8"))
    return base64.b64encode(digest.digest(), b"ab")[0:8].decode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import master games from PGN into lila-openingexplorer /import/masters.",
    )
    parser.add_argument("input_pgn", help="Input PGN file path")
    parser.add_argument(
        "date_fails",
        nargs="?",
        default=DATE_FAILS_PGN,
        help=f"Append date-skip games here (default: {DATE_FAILS_PGN})",
    )
    parser.add_argument(
        "result_fails",
        nargs="?",
        default=RESULT_FAILS_PGN,
        help=f"Append bad Result games here (default: {RESULT_FAILS_PGN})",
    )
    parser.add_argument(
        "header_fails",
        nargs="?",
        default=HEADER_FAILS_PGN,
        help=f"Append header-parse failures here (default: {HEADER_FAILS_PGN})",
    )
    parser.add_argument(
        "--rating-fails",
        dest="rating_fails",
        default=RATING_FAILS_PGN,
        help=f"Append rating policy rejects here (default: {RATING_FAILS_PGN})",
    )
    parser.add_argument(
        "legacy_5th",
        nargs="?",
        default=None,
        help="Ignored (backward compatibility)",
    )
    parser.add_argument(
        "--last-id",
        dest="last_id",
        default=None,
        metavar="ID",
        help=(
            "Resume: skip PUTs until this import id is seen (same id as printed on stdout); "
            "that game is skipped (already loaded); import continues with the following games. "
            "Requires stable PGN order."
        ),
    )
    args = parser.parse_args()

    main(
        open(args.input_pgn, errors="ignore"),
        date_fails_path=args.date_fails,
        result_fails_path=args.result_fails,
        header_fails_path=args.header_fails,
        rating_fails_path=args.rating_fails,
        request_fails_path=args.legacy_5th or REQUEST_FAILS_PGN,
        last_id=args.last_id,
    )
