#!/usr/bin/env python3
"""
Find PGN games whose Result tag is not one of:
  - 1-0
  - 0-1
  - 1/2-1/2

Usage:
  python3 find_invalid_results.py input.pgn
  python3 find_invalid_results.py input.pgn invalid_results.pgn
"""

import chess.pgn
import sys

VALID_RESULTS = {"1-0", "0-1", "1/2-1/2"}


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: find_invalid_results.py input.pgn [output.pgn]", file=sys.stderr)
        sys.exit(1)

    in_path = sys.argv[1]
    out = open(sys.argv[2], "w", encoding="utf-8") if len(sys.argv) > 2 else None

    invalid_count = 0
    game_index = 0

    with open(in_path, errors="replace", encoding="utf-8") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break

            game_index += 1
            result = game.headers.get("Result", "").strip()
            if result in VALID_RESULTS:
                continue

            invalid_count += 1
            event = game.headers.get("Event", "?")
            white = game.headers.get("White", "?")
            black = game.headers.get("Black", "?")
            date = game.headers.get("Date", "?")
            print(
                f"game #{game_index}: Result='{result or '<missing>'}' "
                f"Date='{date}' White='{white}' Black='{black}' Event='{event}'"
            )

            if out is not None:
                print(game, file=out, end="")
                out.write("\n\n")

    if out is not None:
        out.close()

    print(f"\nScanned {game_index} games. Found {invalid_count} invalid Result tag(s).")


if __name__ == "__main__":
    main()
