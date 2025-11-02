#!/usr/bin/env python3
"""
Debug script to analyze move processing issues
"""

import chess
from pathlib import Path
from src.parsers.pgn_parser import PGNParser

def debug_single_game():
    """Debug a single game to see move processing"""
    parser = PGNParser()
    
    # Parse a simple game file
    file_path = Path("data/lichess_pgn_2021.01.16_HenrikofSweden_vs_v7p3r.0sYPB1Tj.pgn")
    
    print(f"Parsing {file_path}...")
    games = parser.parse_file(file_path)
    
    if not games:
        print("No games found!")
        return
        
    game = games[0]
    print(f"\nGame: {game.metadata.white} vs {game.metadata.black}")
    print(f"Player color: {game.player_color}")
    print(f"Total moves: {len(game.moves)}")
    
    # Reconstruct the game
    board = chess.Board()
    print(f"\nStarting position: {board.fen()}")
    
    for i, move_data in enumerate(game.moves[:10]):  # First 10 moves
        print(f"\nMove {i+1}: {move_data.color} {move_data.san} ({move_data.uci})")
        print(f"Position before: {board.fen()}")
        
        try:
            # Try to parse as SAN first
            move = board.parse_san(move_data.san)
            print(f"✓ SAN parsed successfully: {move}")
        except Exception as san_error:
            try:
                # Try UCI
                move = chess.Move.from_uci(move_data.uci)
                if move in board.legal_moves:
                    print(f"✓ UCI parsed successfully: {move}")
                else:
                    print(f"✗ UCI move is illegal: {move}")
                    print(f"Legal moves: {list(board.legal_moves)}")
                    break
            except Exception as uci_error:
                print(f"✗ Both SAN and UCI failed:")
                print(f"  SAN error: {san_error}")
                print(f"  UCI error: {uci_error}")
                break
        
        # Make the move
        board.push(move)
        print(f"Position after: {board.fen()}")

if __name__ == "__main__":
    debug_single_game()