"""
Test script for Chess Strength Analyzer components

Tests PGN parsing and Stockfish integration with user's data.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from parsers.pgn_parser import PGNParser, GameFilter
from analyzers.stockfish_analyzer import StockfishAnalyzer
import chess

def test_pgn_parsing():
    """Test PGN parsing with user's data"""
    print("=== Testing PGN Parser ===")
    
    parser = PGNParser("v7p3r")
    
    # Test with the largest file first
    data_dir = Path("data")
    test_file = data_dir / "lichess_v7p3r_2025-10-02.pgn"
    
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return []
    
    print(f"Parsing {test_file}...")
    games = parser.parse_file(test_file)
    
    print(f"Parsed {len(games)} games")
    
    if games:
        # Show sample game info
        game = games[0]
        print(f"\nSample game:")
        print(f"  Event: {game.metadata.event}")
        print(f"  Players: {game.metadata.white} vs {game.metadata.black}")
        print(f"  Date: {game.metadata.date}")
        print(f"  Result: {game.metadata.result}")
        print(f"  Player color: {game.player_color}")
        print(f"  Opening: {game.metadata.opening}")
        print(f"  Time control: {game.metadata.time_control}")
        print(f"  Moves: {len(game.moves)}")
        
        # Show first few moves
        if game.moves:
            print(f"  First moves: {', '.join([f'{i+1}.{m.san}' for i, m in enumerate(game.moves[:6])])}")
            
        # Test filtering
        player_games = GameFilter.filter_by_player(games, "v7p3r")
        print(f"\nPlayer games: {len(player_games)}")
        
        wins = GameFilter.filter_by_result(player_games, "win")
        losses = GameFilter.filter_by_result(player_games, "loss")
        draws = GameFilter.filter_by_result(player_games, "draw")
        
        print(f"  Wins: {len(wins)}")
        print(f"  Losses: {len(losses)}")
        print(f"  Draws: {len(draws)}")
    
    return games

def test_stockfish_integration():
    """Test Stockfish integration"""
    print("\n=== Testing Stockfish Integration ===")
    
    try:
        # Initialize with the provided path
        stockfish_path = "S:\\Maker Stuff\\Programming\\Chess Engines\\Chess Engine Playground\\engine-tester\\engines\\Stockfish\\stockfish-windows-x86-64-avx2.exe"
        analyzer = StockfishAnalyzer(stockfish_path=stockfish_path, depth=10)
        print("✓ Stockfish initialized successfully")
        
        # Test position analysis
        starting_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        print(f"\nAnalyzing starting position...")
        
        position_analysis = analyzer.analyze_position(starting_fen, multi_pv=5)
        print(f"✓ Position analysis completed in {position_analysis.analysis_time:.2f}s")
        print(f"  Evaluation: {position_analysis.evaluation}")
        print(f"  Top moves: {[f'{m.san} ({m.centipawn_score})' for m in position_analysis.best_moves[:3]]}")
        
        # Test move analysis
        print(f"\nAnalyzing move e2e4...")
        move_analysis = analyzer.analyze_move(starting_fen, "e2e4")
        print(f"✓ Move analysis completed")
        print(f"  Best move: {move_analysis.best_move.san} ({move_analysis.best_move.centipawn_score})")
        print(f"  Played move: {move_analysis.played_move.san} ({move_analysis.played_move.centipawn_score})")
        print(f"  Centipawn loss: {move_analysis.centipawn_loss}")
        print(f"  Classification: {'Blunder' if move_analysis.is_blunder else 'Mistake' if move_analysis.is_mistake else 'Inaccuracy' if move_analysis.is_inaccuracy else 'Good'}")
        
        return analyzer
        
    except Exception as e:
        print(f"✗ Stockfish integration failed: {e}")
        return None

def analyze_sample_game(games, analyzer):
    """Analyze a sample game to test the full pipeline"""
    if not games or not analyzer:
        print("\nSkipping game analysis (missing data or analyzer)")
        return
        
    print("\n=== Analyzing Sample Game ===")
    
    # Find a game where user played
    user_game = None
    for game in games:
        if game.player_color and len(game.moves) > 10:  # Ensure reasonable game length
            user_game = game
            break
    
    if not user_game:
        print("No suitable user games found")
        return
    
    print(f"Analyzing game: {user_game.metadata.white} vs {user_game.metadata.black}")
    print(f"User played as: {user_game.player_color}")
    print(f"Result: {user_game.metadata.result}")
    
    # Analyze first 10 moves to keep test quick
    moves_to_analyze = user_game.moves[:10]
    
    # Reconstruct positions for analysis
    board = chess.Board()
    fens_and_moves = []
    
    for move_data in moves_to_analyze:
        fen_before = board.fen()
        try:
            move = chess.Move.from_uci(move_data.uci)
            fens_and_moves.append((fen_before, move_data.uci))
            board.push(move)
        except Exception as e:
            print(f"Error processing move {move_data.san}: {e}")
            break
    
    if fens_and_moves:
        print(f"Analyzing {len(fens_and_moves)} moves...")
        
        # Analyze the moves
        move_analyses = []
        for i, (fen, move_uci) in enumerate(fens_and_moves):
            try:
                analysis = analyzer.analyze_move(fen, move_uci)
                move_analyses.append(analysis)
                print(f"  Move {i+1}: {analysis.played_move.san} - Loss: {analysis.centipawn_loss}cp")
            except Exception as e:
                print(f"Error analyzing move {i+1}: {e}")
                break
        
        # Calculate basic statistics
        if move_analyses:
            total_loss = sum(ma.centipawn_loss for ma in move_analyses)
            blunders = sum(1 for ma in move_analyses if ma.is_blunder)
            mistakes = sum(1 for ma in move_analyses if ma.is_mistake)
            inaccuracies = sum(1 for ma in move_analyses if ma.is_inaccuracy)
            
            print(f"\nQuick Analysis Results:")
            print(f"  Total centipawn loss: {total_loss}")
            print(f"  Average loss per move: {total_loss/len(move_analyses):.1f}")
            print(f"  Blunders: {blunders}")
            print(f"  Mistakes: {mistakes}")
            print(f"  Inaccuracies: {inaccuracies}")
            print(f"  Good moves: {len(move_analyses) - blunders - mistakes - inaccuracies}")

def main():
    """Run all tests"""
    print("Chess Strength Analyzer - Component Testing")
    print("=" * 50)
    
    # Test PGN parsing
    games = test_pgn_parsing()
    
    # Test Stockfish integration
    analyzer = test_stockfish_integration()
    
    # Test full pipeline with sample game
    analyze_sample_game(games, analyzer)
    
    print("\n" + "=" * 50)
    print("Testing completed!")
    
    if games and analyzer:
        print(f"\n✓ Successfully parsed {len(games)} games")
        print("✓ Stockfish integration working")
        print("✓ Basic analysis pipeline functional")
        print("\nReady to proceed with full implementation!")
    else:
        print("\n✗ Some components failed - check errors above")

if __name__ == "__main__":
    main()