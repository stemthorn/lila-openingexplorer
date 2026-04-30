import chess.pgn

# Load engine keywords
with open("./pgn/engine_keywords.txt", encoding="utf-8") as f:
    ENGINE_KEYWORDS = {line.strip().lower() for line in f if line.strip()}

def is_engine_game(game: chess.pgn.Game) -> bool:
    # Primary: WhiteType / BlackType
    if game.headers.get("WhiteType", "").strip().lower() == "program" or \
       game.headers.get("BlackType", "").strip().lower() == "program":
        return True
    
    # Fallback: name matching
    white = game.headers.get("White", "").lower()
    black = game.headers.get("Black", "").lower()
    for kw in ENGINE_KEYWORDS:
        if kw in white or kw in black:
            return True
    return False

# Main processing
input_pgn = "./pgn/big-fixed.pgn"
human_output = "./pgn/human_games.pgn"
engine_output = "./pgn/engine_games.pgn"

with open(input_pgn, encoding="utf-8", errors="replace") as pgn_file, \
     open(human_output, "w", encoding="utf-8") as human_f, \
     open(engine_output, "w", encoding="utf-8") as engine_f:
    
    human_exporter = chess.pgn.FileExporter(human_f)
    engine_exporter = chess.pgn.FileExporter(engine_f)
    
    while True:
        game = chess.pgn.read_game(pgn_file)
        if game is None:
            break  # end of file
        
        if is_engine_game(game):
            game.accept(engine_exporter)
        else:
            game.accept(human_exporter)

print("Done! Engine games →", engine_output, " | Human games →", human_output)