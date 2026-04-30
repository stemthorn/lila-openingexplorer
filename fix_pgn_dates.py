#!/usr/bin/env python3
"""
Rewrite a multi-game PGN: set [Date] from the best available tag (Date, else EventDate,
UTCDate, SourceDate, DateTime). See pgn_date_resolve.py for exact rules.

Usage:
  python3 fix_pgn_dates.py input.pgn output.pgn
  python3 fix_pgn_dates.py input.pgn   # writes to stdout
"""

import chess.pgn
import sys

from pgn_date_resolve import format_pgn_date_for_header, resolve_pgn_date


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: fix_pgn_dates.py input.pgn [output.pgn]", file=sys.stderr)
        sys.exit(1)
    in_path = sys.argv[1]
    out = open(sys.argv[2], "w", encoding="utf-8") if len(sys.argv) > 2 else sys.stdout
    with open(in_path, errors="replace", encoding="utf-8") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            resolved = resolve_pgn_date(game.headers)
            game.headers["Date"] = format_pgn_date_for_header(resolved)
            print(game, file=out, end="")
            out.write("\n\n")
    if out is not sys.stdout:
        out.close()


if __name__ == "__main__":
    main()
