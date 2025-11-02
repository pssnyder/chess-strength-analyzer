"""
Stockfish Integration for Chess Analysis

Provides move evaluation, top alternatives analysis, and position assessment
using the Stockfish chess engine.
"""

import chess
import chess.engine
from stockfish import Stockfish
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from pathlib import Path
import json
import time

@dataclass
class MoveEvaluation:
    """Evaluation of a single move"""
    move: str  # UCI notation
    san: str   # Standard Algebraic Notation
    centipawn_score: Optional[int]  # Engine evaluation in centipawns
    mate_score: Optional[int]      # Mate in X moves (if applicable)
    depth: int                     # Search depth
    rank: int                      # Rank among alternatives (1 = best)

@dataclass
class PositionAnalysis:
    """Complete analysis of a chess position"""
    fen: str
    best_moves: List[MoveEvaluation]  # Top 5 moves
    evaluation: int                   # Position evaluation in centipawns
    mate_score: Optional[int]         # Mate in X if applicable
    depth: int
    analysis_time: float

@dataclass
class MoveAnalysis:
    """Analysis of a move compared to best alternatives"""
    played_move: MoveEvaluation
    best_move: MoveEvaluation
    centipawn_loss: int              # Accuracy loss from best move
    is_blunder: bool                 # True if significant mistake
    is_mistake: bool                 # True if moderate mistake
    is_inaccuracy: bool              # True if slight inaccuracy
    alternative_moves: List[MoveEvaluation]  # Other good options

class StockfishAnalyzer:
    """Stockfish engine wrapper for chess analysis"""
    
    def __init__(self, 
                 stockfish_path: Optional[str] = None,
                 depth: int = 15,
                 time_limit: float = 1.0,
                 threads: int = 1,
                 hash_size: int = 128):
        """
        Initialize Stockfish analyzer
        
        Args:
            stockfish_path: Path to Stockfish executable
            depth: Search depth for analysis
            time_limit: Time limit per position in seconds
            threads: Number of CPU threads to use
            hash_size: Hash table size in MB
        """
        self.depth = depth
        self.time_limit = time_limit
        self.logger = logging.getLogger(__name__)
        
        # Initialize Stockfish
        try:
            if stockfish_path:
                self.stockfish = Stockfish(path=stockfish_path)
            else:
                # Try common locations
                self.stockfish = self._find_stockfish()
            
            # Configure engine settings
            self.stockfish.set_depth(depth)
            if hasattr(self.stockfish, 'set_num_threads'):
                self.stockfish.set_num_threads(threads)
            
            self.logger.info(f"Stockfish initialized with depth {depth}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Stockfish: {e}")
            raise
    
    def _find_stockfish(self) -> Stockfish:
        """Try to find Stockfish in common locations"""
        common_paths = [
            "S:\\Maker Stuff\\Programming\\Chess Engines\\Chess Engine Playground\\engine-tester\\engines\\Stockfish\\stockfish-windows-x86-64-avx2.exe",
            "stockfish",
            "stockfish.exe", 
            "/usr/local/bin/stockfish",
            "/opt/homebrew/bin/stockfish",
            "C:\\Program Files\\Stockfish\\stockfish.exe"
        ]
        
        for path in common_paths:
            try:
                sf = Stockfish(path=path)
                self.logger.info(f"Found Stockfish at: {path}")
                return sf
            except:
                continue
        
        raise Exception("Stockfish not found. Please install Stockfish or provide path.")
    
    def analyze_position(self, fen: str, multi_pv: int = 5) -> PositionAnalysis:
        """
        Analyze a chess position and return top moves
        
        Args:
            fen: Position in FEN notation
            multi_pv: Number of top moves to analyze
        
        Returns:
            PositionAnalysis with best moves and evaluation
        """
        start_time = time.time()
        
        try:
            # Validate FEN before sending to Stockfish
            try:
                test_board = chess.Board(fen)
                if not test_board.is_valid():
                    self.logger.warning(f"Invalid position: {fen}")
                    return self._empty_position_analysis(fen, start_time)
            except Exception as e:
                self.logger.warning(f"FEN parsing error for {fen}: {e}")
                return self._empty_position_analysis(fen, start_time)
            
            # Reinitialize Stockfish if it crashed
            if not self._is_stockfish_alive():
                self.logger.warning("Stockfish process not alive, reinitializing...")
                self._reinitialize_stockfish()
            
            self.stockfish.set_fen_position(fen)
            
            # Get top moves with error handling
            try:
                top_moves = self.stockfish.get_top_moves(multi_pv)
            except Exception as e:
                self.logger.warning(f"Stockfish get_top_moves failed for {fen}: {e}")
                # Try to reinitialize and retry once
                self._reinitialize_stockfish()
                try:
                    self.stockfish.set_fen_position(fen)
                    top_moves = self.stockfish.get_top_moves(multi_pv)
                except Exception as e2:
                    self.logger.error(f"Stockfish failed again for {fen}: {e2}")
                    return self._empty_position_analysis(fen, start_time)
            
            if not top_moves:
                # Position might be terminal or invalid
                try:
                    evaluation = self.stockfish.get_evaluation()
                except:
                    evaluation = None
                    
                return PositionAnalysis(
                    fen=fen,
                    best_moves=[],
                    evaluation=evaluation.get('value', 0) if evaluation else 0,
                    mate_score=evaluation.get('mate') if evaluation else None,
                    depth=self.depth,
                    analysis_time=time.time() - start_time
                )
            
            # Convert to MoveEvaluation objects
            move_evaluations = []
            for i, move_data in enumerate(top_moves):
                move_eval = MoveEvaluation(
                    move=move_data['Move'],
                    san=self._uci_to_san(fen, move_data['Move']),
                    centipawn_score=move_data.get('Centipawn'),
                    mate_score=move_data.get('Mate'),
                    depth=self.depth,
                    rank=i + 1
                )
                move_evaluations.append(move_eval)
            
            # Get overall position evaluation
            try:
                evaluation = self.stockfish.get_evaluation()
                eval_score = evaluation.get('value', 0) if evaluation else 0
                mate_score = evaluation.get('mate') if evaluation else None
            except:
                eval_score = 0
                mate_score = None
            
            return PositionAnalysis(
                fen=fen,
                best_moves=move_evaluations,
                evaluation=eval_score,
                mate_score=mate_score,
                depth=self.depth,
                analysis_time=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing position {fen}: {e}")
            return self._empty_position_analysis(fen, start_time)
    
    def analyze_move(self, before_fen: str, move_uci: str) -> MoveAnalysis:
        """
        Analyze a specific move compared to best alternatives
        
        Args:
            before_fen: Position before the move
            move_uci: Move in UCI notation
        
        Returns:
            MoveAnalysis with move quality assessment
        """
        # Get position analysis before move
        position_analysis = self.analyze_position(before_fen)
        
        if not position_analysis.best_moves:
            # Can't analyze if no moves available
            played_eval = MoveEvaluation(
                move=move_uci,
                san=self._uci_to_san(before_fen, move_uci),
                centipawn_score=0,
                mate_score=None,
                depth=self.depth,
                rank=1
            )
            return MoveAnalysis(
                played_move=played_eval,
                best_move=played_eval,
                centipawn_loss=0,
                is_blunder=False,
                is_mistake=False,
                is_inaccuracy=False,
                alternative_moves=[]
            )
        
        best_move = position_analysis.best_moves[0]
        
        # Find the played move in the list or evaluate it separately
        played_move_eval = None
        for move_eval in position_analysis.best_moves:
            if move_eval.move == move_uci:
                played_move_eval = move_eval
                break
        
        if not played_move_eval:
            # Move not in top 5, evaluate separately
            played_move_eval = self._evaluate_specific_move(before_fen, move_uci)
        
        # Calculate centipawn loss
        best_score = best_move.centipawn_score or 0
        played_score = played_move_eval.centipawn_score or 0
        
        # Adjust for side to move (negative scores are bad for white)
        board = chess.Board(before_fen)
        if board.turn == chess.BLACK:
            best_score = -best_score
            played_score = -played_score
        
        centipawn_loss = max(0, best_score - played_score)
        
        # Classify move quality
        is_blunder = centipawn_loss >= 300
        is_mistake = 100 <= centipawn_loss < 300
        is_inaccuracy = 50 <= centipawn_loss < 100
        
        return MoveAnalysis(
            played_move=played_move_eval,
            best_move=best_move,
            centipawn_loss=centipawn_loss,
            is_blunder=is_blunder,
            is_mistake=is_mistake,
            is_inaccuracy=is_inaccuracy,
            alternative_moves=position_analysis.best_moves[1:]  # Exclude best move
        )
    
    def _evaluate_specific_move(self, fen: str, move_uci: str) -> MoveEvaluation:
        """Evaluate a specific move"""
        try:
            # Make the move and evaluate resulting position
            board = chess.Board(fen)
            move = chess.Move.from_uci(move_uci)
            board.push(move)
            
            # Evaluate the resulting position
            self.stockfish.set_fen_position(board.fen())
            evaluation = self.stockfish.get_evaluation()
            
            score = evaluation.get('value', 0) if evaluation else 0
            # Flip score since we're evaluating from opponent's perspective
            score = -score
            
            return MoveEvaluation(
                move=move_uci,
                san=board.san(move),
                centipawn_score=score,
                mate_score=evaluation.get('mate') if evaluation else None,
                depth=self.depth,
                rank=999  # Unknown rank
            )
            
        except Exception as e:
            self.logger.error(f"Error evaluating move {move_uci}: {e}")
            return MoveEvaluation(
                move=move_uci,
                san=move_uci,
                centipawn_score=0,
                mate_score=None,
                depth=self.depth,
                rank=999
            )
    
    def _uci_to_san(self, fen: str, uci_move: str) -> str:
        """Convert UCI move to Standard Algebraic Notation"""
        try:
            board = chess.Board(fen)
            move = chess.Move.from_uci(uci_move)
            if move in board.legal_moves:
                return board.san(move)
            else:
                self.logger.warning(f"Illegal move {uci_move} in position {fen}")
                return uci_move
        except Exception as e:
            self.logger.warning(f"Error converting UCI to SAN for {uci_move}: {e}")
            return uci_move
    
    def _is_stockfish_alive(self) -> bool:
        """Check if Stockfish process is still alive"""
        try:
            # Try a simple command to test if Stockfish is responsive
            self.stockfish.get_evaluation()
            return True
        except:
            return False
    
    def _reinitialize_stockfish(self):
        """Reinitialize Stockfish if it crashed"""
        try:
            # Try to close existing instance
            if hasattr(self.stockfish, '_stockfish') and self.stockfish._stockfish:
                try:
                    self.stockfish._stockfish.terminate()
                except:
                    pass
            
            # Reinitialize
            self.stockfish = self._find_stockfish()
            self.stockfish.set_depth(self.depth)
            self.logger.info("Stockfish reinitialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to reinitialize Stockfish: {e}")
            raise
    
    def _empty_position_analysis(self, fen: str, start_time: float) -> PositionAnalysis:
        """Return empty position analysis for error cases"""
        return PositionAnalysis(
            fen=fen,
            best_moves=[],
            evaluation=0,
            mate_score=None,
            depth=self.depth,
            analysis_time=time.time() - start_time
        )
    
    def batch_analyze_game(self, fens_and_moves: List[Tuple[str, str]]) -> List[MoveAnalysis]:
        """
        Analyze multiple moves in batch for efficiency
        
        Args:
            fens_and_moves: List of (fen_before_move, move_uci) tuples
        
        Returns:
            List of MoveAnalysis results
        """
        results = []
        
        for i, (fen, move) in enumerate(fens_and_moves):
            try:
                analysis = self.analyze_move(fen, move)
                results.append(analysis)
                
                # Progress logging for long games
                if i % 10 == 0:
                    self.logger.debug(f"Analyzed {i}/{len(fens_and_moves)} moves")
                    
            except Exception as e:
                self.logger.error(f"Error analyzing move {i}: {e}")
                # Create dummy analysis to maintain list integrity
                dummy_eval = MoveEvaluation(
                    move=move,
                    san=move,
                    centipawn_score=0,
                    mate_score=None,
                    depth=self.depth,
                    rank=1
                )
                results.append(MoveAnalysis(
                    played_move=dummy_eval,
                    best_move=dummy_eval,
                    centipawn_loss=0,
                    is_blunder=False,
                    is_mistake=False,
                    is_inaccuracy=False,
                    alternative_moves=[]
                ))
        
        return results
    
    def get_opening_book_move(self, fen: str) -> Optional[str]:
        """Get opening book move if position is in book"""
        try:
            self.stockfish.set_fen_position(fen)
            # This would require extending stockfish package or using book
            # For now, return None
            return None
        except:
            return None

class EnginePool:
    """Pool of Stockfish engines for parallel analysis"""
    
    def __init__(self, pool_size: int = 4, **engine_kwargs):
        self.pool_size = pool_size
        self.engines = []
        self.logger = logging.getLogger(__name__)
        
        # Initialize engine pool
        for i in range(pool_size):
            try:
                engine = StockfishAnalyzer(**engine_kwargs)
                self.engines.append(engine)
            except Exception as e:
                self.logger.error(f"Failed to create engine {i}: {e}")
        
        if not self.engines:
            raise Exception("Failed to create any engines")
        
        self.logger.info(f"Created engine pool with {len(self.engines)} engines")
    
    def get_engine(self) -> StockfishAnalyzer:
        """Get an available engine (simple round-robin for now)"""
        import random
        return random.choice(self.engines)
    
    def analyze_games_parallel(self, games_data) -> List[List[MoveAnalysis]]:
        """Analyze multiple games in parallel (future implementation)"""
        # This would use threading/multiprocessing for true parallelism
        # For now, just analyze sequentially
        results = []
        engine = self.get_engine()
        
        for game_moves in games_data:
            game_analysis = engine.batch_analyze_game(game_moves)
            results.append(game_analysis)
        
        return results

if __name__ == "__main__":
    # Test the analyzer
    analyzer = StockfishAnalyzer(depth=10)
    
    # Test position analysis
    starting_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    position_analysis = analyzer.analyze_position(starting_fen)
    
    print(f"Position evaluation: {position_analysis.evaluation}")
    print(f"Top moves: {[m.san for m in position_analysis.best_moves[:3]]}")
    
    # Test move analysis
    move_analysis = analyzer.analyze_move(starting_fen, "e2e4")
    print(f"Move e4 centipawn loss: {move_analysis.centipawn_loss}")
    print(f"Is blunder: {move_analysis.is_blunder}")