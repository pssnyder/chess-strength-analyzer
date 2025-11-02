"""
Performance Metrics Calculator

Calculates comprehensive chess performance metrics including:
- Accuracy percentage
- Blunder/mistake/inaccuracy rates  
- Time management analysis
- Opening performance
- Rating progression
- Performance vs different opponents
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from collections import defaultdict, Counter

from parsers.pgn_parser import ParsedGame, GameMetadata, MoveData
from analyzers.stockfish_analyzer import MoveAnalysis, StockfishAnalyzer

@dataclass
class PerformanceMetrics:
    """Complete performance metrics for a player"""
    # Overall statistics
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    
    # Move quality metrics
    total_moves: int
    average_centipawn_loss: float
    accuracy_percentage: float
    blunder_rate: float
    mistake_rate: float
    inaccuracy_rate: float
    
    # Time management
    average_move_time: Optional[float]
    time_pressure_performance: Optional[float]  # Performance when <30s left
    
    # Opening performance
    opening_stats: Dict[str, Dict[str, Any]]  # ECO code -> stats
    
    # Rating and progression
    rating_progression: List[Tuple[datetime, int]]
    current_rating: Optional[int]
    rating_change: Optional[int]
    
    # Opponent analysis
    performance_by_rating_range: Dict[str, Dict[str, Any]]
    
    # Time control analysis
    performance_by_time_control: Dict[str, Dict[str, Any]]
    
    # Trend analysis
    recent_form: Dict[str, Any]  # Last 20 games
    improvement_areas: List[str]
    strengths: List[str]

@dataclass
class GameAnalysis:
    """Analysis results for a single game"""
    game: ParsedGame
    move_analyses: List[MoveAnalysis]
    total_centipawn_loss: int
    accuracy_percentage: float
    blunders: int
    mistakes: int
    inaccuracies: int
    average_move_time: Optional[float]
    time_trouble_moves: int  # Moves made with <30s on clock
    opening_accuracy: float  # Accuracy in first 10 moves
    middlegame_accuracy: float  # Moves 11-40
    endgame_accuracy: float  # Moves 40+

class PerformanceCalculator:
    """Calculate comprehensive chess performance metrics"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def analyze_games_batch(self, games: List[ParsedGame], 
                          analyzer: StockfishAnalyzer,
                          max_games: Optional[int] = None) -> List[GameAnalysis]:
        """Analyze multiple games for performance metrics"""
        
        if max_games:
            games = games[:max_games]
            
        game_analyses = []
        
        for i, game in enumerate(games):
            try:
                self.logger.info(f"Analyzing game {i+1}/{len(games)}: {game.metadata.white} vs {game.metadata.black}")
                
                analysis = self.analyze_single_game(game, analyzer)
                if analysis:
                    game_analyses.append(analysis)
                    
            except Exception as e:
                self.logger.error(f"Error analyzing game {i+1}: {e}")
                continue
        
        return game_analyses
    
    def analyze_single_game(self, game: ParsedGame, analyzer: StockfishAnalyzer) -> Optional[GameAnalysis]:
        """Analyze a single game for performance metrics"""
        
        if not game.player_color or len(game.moves) < 5:
            return None
            
        # Reconstruct game positions for analysis
        import chess
        board = chess.Board()
        fens_and_moves = []
        player_moves = []
        
        try:
            for move_data in game.moves:
                # Record the position before this move
                fen_before = board.fen()
                
                # Parse the move
                try:
                    move = board.parse_san(move_data.san)
                except Exception:
                    try:
                        move = chess.Move.from_uci(move_data.uci)
                        if move not in board.legal_moves:
                            self.logger.warning(f"Illegal UCI move {move_data.uci} in position {fen_before}")
                            continue
                    except Exception as e:
                        self.logger.warning(f"Could not parse move {move_data.san} ({move_data.uci}): {e}")
                        continue
                
                # If this is the player's move, record it for analysis
                if move_data.color == game.player_color:
                    fens_and_moves.append((fen_before, move.uci()))
                    player_moves.append(move_data)
                
                # Make the move on the board to advance the position
                board.push(move)
                
                # Safety check to prevent infinite games
                if len(fens_and_moves) > 100:  # Max 100 player moves per game
                    self.logger.warning(f"Truncating analysis at {len(fens_and_moves)} player moves")
                    break
                    
        except Exception as e:
            self.logger.error(f"Error reconstructing game: {e}")
            return None
        
        if not fens_and_moves:
            self.logger.warning(f"No valid moves found for player {game.player_color}")
            return None
        
        # Analyze the moves with robust error handling
        try:
            move_analyses = analyzer.batch_analyze_game(fens_and_moves)
        except Exception as e:
            self.logger.error(f"Error in batch analysis: {e}")
            return None
        
        if not move_analyses:
            self.logger.warning("No moves could be analyzed")
            return None
        
        # Calculate metrics - adapted for MoveAnalysis objects
        total_centipawn_loss = sum(ma.centipawn_loss for ma in move_analyses)
        blunders = sum(1 for ma in move_analyses if ma.is_blunder)
        
        # Calculate mistakes and inaccuracies based on centipawn loss
        mistakes = sum(1 for ma in move_analyses 
                      if not ma.is_blunder and ma.centipawn_loss >= 100)
        inaccuracies = sum(1 for ma in move_analyses 
                          if not ma.is_blunder and ma.centipawn_loss < 100 and ma.centipawn_loss >= 50)
        
        # Calculate accuracy (100 - average centipawn loss per move, capped at 0-100)
        avg_loss = total_centipawn_loss / len(move_analyses)
        accuracy = max(0, min(100, 100 - (avg_loss / 3)))  # Rough accuracy formula
        
        # Time analysis - only include valid move times
        valid_move_times = [m.move_time for m in player_moves 
                           if m.move_time and m.move_time > 0 and m.move_time < 3600]  # Under 1 hour
        average_move_time = float(np.mean(valid_move_times)) if valid_move_times else None
        
        # Time trouble analysis (moves with <30s remaining)
        time_trouble_moves = 0
        for move_data in player_moves:
            if move_data.clock_time and 0 < move_data.clock_time < 30:
                time_trouble_moves += 1
        
        # Phase-based accuracy
        opening_moves = move_analyses[:min(10, len(move_analyses))]
        middlegame_moves = move_analyses[10:min(40, len(move_analyses))]
        endgame_moves = move_analyses[40:] if len(move_analyses) > 40 else []
        
        opening_accuracy = self._calculate_phase_accuracy(opening_moves)
        middlegame_accuracy = self._calculate_phase_accuracy(middlegame_moves)
        endgame_accuracy = self._calculate_phase_accuracy(endgame_moves)
        
        return GameAnalysis(
            game=game,
            move_analyses=move_analyses,
            total_centipawn_loss=total_centipawn_loss,
            accuracy_percentage=accuracy,
            blunders=blunders,
            mistakes=mistakes,
            inaccuracies=inaccuracies,
            average_move_time=average_move_time,
            time_trouble_moves=time_trouble_moves,
            opening_accuracy=opening_accuracy,
            middlegame_accuracy=middlegame_accuracy,
            endgame_accuracy=endgame_accuracy
        )
    
    def _calculate_phase_accuracy(self, moves: List[MoveAnalysis]) -> float:
        """Calculate accuracy for a specific game phase"""
        if not moves:
            return 0.0
        
        total_loss = sum(ma.centipawn_loss for ma in moves)
        avg_loss = total_loss / len(moves)
        return max(0, min(100, 100 - (avg_loss / 3)))
    
    def calculate_comprehensive_metrics(self, game_analyses: List[GameAnalysis]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics from game analyses"""
        
        if not game_analyses:
            return self._empty_metrics()
        
        # Basic game statistics
        total_games = len(game_analyses)
        wins = sum(1 for ga in game_analyses if self._is_win(ga.game))
        losses = sum(1 for ga in game_analyses if self._is_loss(ga.game))
        draws = total_games - wins - losses
        win_rate = wins / total_games if total_games > 0 else 0.0
        
        # Move quality metrics
        all_moves = []
        for ga in game_analyses:
            all_moves.extend(ga.move_analyses)
        
        total_moves = len(all_moves)
        total_centipawn_loss = sum(ma.centipawn_loss for ma in all_moves)
        average_centipawn_loss = total_centipawn_loss / total_moves if total_moves > 0 else 0
        
        blunders = sum(ga.blunders for ga in game_analyses)
        mistakes = sum(ga.mistakes for ga in game_analyses)
        inaccuracies = sum(ga.inaccuracies for ga in game_analyses)
        
        blunder_rate = blunders / total_moves if total_moves > 0 else 0
        mistake_rate = mistakes / total_moves if total_moves > 0 else 0
        inaccuracy_rate = inaccuracies / total_moves if total_moves > 0 else 0
        
        # Overall accuracy
        accuracy_percentage = float(np.mean([ga.accuracy_percentage for ga in game_analyses]))
        
        # Time management
        move_times = []
        for ga in game_analyses:
            if ga.average_move_time:
                move_times.append(ga.average_move_time)
        average_move_time = float(np.mean(move_times)) if move_times else None
        
        # Opening analysis
        opening_stats = self._analyze_openings(game_analyses)
        
        # Rating progression
        rating_progression = self._calculate_rating_progression(game_analyses)
        current_rating = rating_progression[-1][1] if rating_progression else None
        rating_change = None
        if len(rating_progression) > 1:
            rating_change = rating_progression[-1][1] - rating_progression[0][1]
        
        # Performance by opponent rating
        performance_by_rating = self._analyze_performance_by_rating(game_analyses)
        
        # Performance by time control
        performance_by_time_control = self._analyze_performance_by_time_control(game_analyses)
        
        # Recent form (last 20 games)
        recent_games = game_analyses[-20:] if len(game_analyses) >= 20 else game_analyses
        recent_form = self._analyze_recent_form(recent_games)
        
        # Identify strengths and improvement areas
        strengths, improvement_areas = self._identify_strengths_and_weaknesses(game_analyses)
        
        return PerformanceMetrics(
            total_games=total_games,
            wins=wins,
            losses=losses,
            draws=draws,
            win_rate=win_rate,
            total_moves=total_moves,
            average_centipawn_loss=average_centipawn_loss,
            accuracy_percentage=accuracy_percentage,
            blunder_rate=blunder_rate,
            mistake_rate=mistake_rate,
            inaccuracy_rate=inaccuracy_rate,
            average_move_time=average_move_time,
            time_pressure_performance=None,  # TODO: Calculate
            opening_stats=opening_stats,
            rating_progression=rating_progression,
            current_rating=current_rating,
            rating_change=rating_change,
            performance_by_rating_range=performance_by_rating,
            performance_by_time_control=performance_by_time_control,
            recent_form=recent_form,
            improvement_areas=improvement_areas,
            strengths=strengths
        )
    
    def _is_win(self, game: ParsedGame) -> bool:
        """Check if the game was a win for the player"""
        if game.player_color == "white":
            return game.metadata.result == "1-0"
        else:
            return game.metadata.result == "0-1"
    
    def _is_loss(self, game: ParsedGame) -> bool:
        """Check if the game was a loss for the player"""
        if game.player_color == "white":
            return game.metadata.result == "0-1"
        else:
            return game.metadata.result == "1-0"
    
    def _analyze_openings(self, game_analyses: List[GameAnalysis]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by opening"""
        opening_data = defaultdict(lambda: {
            'games': 0, 'wins': 0, 'losses': 0, 'draws': 0,
            'avg_accuracy': 0.0, 'total_accuracy': 0.0
        })
        
        for ga in game_analyses:
            eco = ga.game.metadata.eco or "Unknown"
            opening = ga.game.metadata.opening or "Unknown Opening"
            
            key = f"{eco}: {opening}"
            stats = opening_data[key]
            
            stats['games'] += 1
            stats['total_accuracy'] += ga.opening_accuracy
            
            if self._is_win(ga.game):
                stats['wins'] += 1
            elif self._is_loss(ga.game):
                stats['losses'] += 1
            else:
                stats['draws'] += 1
        
        # Calculate averages and win rates
        for key, stats in opening_data.items():
            stats['avg_accuracy'] = stats['total_accuracy'] / stats['games']
            stats['win_rate'] = stats['wins'] / stats['games']
            del stats['total_accuracy']  # Remove intermediate calculation
        
        return dict(opening_data)
    
    def _calculate_rating_progression(self, game_analyses: List[GameAnalysis]) -> List[Tuple[datetime, int]]:
        """Calculate rating progression over time"""
        progression = []
        
        for ga in game_analyses:
            date = ga.game.metadata.date
            
            # Get player's rating from the game
            if ga.game.player_color == "white":
                rating = ga.game.metadata.white_elo
            else:
                rating = ga.game.metadata.black_elo
            
            if rating:
                progression.append((date, rating))
        
        # Sort by date
        progression.sort(key=lambda x: x[0])
        
        return progression
    
    def _analyze_performance_by_rating(self, game_analyses: List[GameAnalysis]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance against different rating ranges"""
        rating_ranges = {
            "Under 1200": (0, 1199),
            "1200-1399": (1200, 1399),
            "1400-1599": (1400, 1599),
            "1600-1799": (1600, 1799),
            "1800+": (1800, 9999)
        }
        
        performance = {}
        
        for range_name, (min_rating, max_rating) in rating_ranges.items():
            games_in_range = []
            
            for ga in game_analyses:
                # Get opponent rating
                if ga.game.player_color == "white":
                    opp_rating = ga.game.metadata.black_elo
                else:
                    opp_rating = ga.game.metadata.white_elo
                
                if opp_rating and min_rating <= opp_rating <= max_rating:
                    games_in_range.append(ga)
            
            if games_in_range:
                wins = sum(1 for ga in games_in_range if self._is_win(ga.game))
                total = len(games_in_range)
                avg_accuracy = np.mean([ga.accuracy_percentage for ga in games_in_range])
                
                performance[range_name] = {
                    'games': total,
                    'wins': wins,
                    'win_rate': wins / total,
                    'avg_accuracy': avg_accuracy
                }
        
        return performance
    
    def _analyze_performance_by_time_control(self, game_analyses: List[GameAnalysis]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by time control"""
        time_control_data = defaultdict(lambda: {
            'games': 0, 'wins': 0, 'total_accuracy': 0.0
        })
        
        for ga in game_analyses:
            tc = ga.game.metadata.time_control or "Unknown"
            
            # Categorize time controls
            if "+" in tc:
                if any(fast in tc for fast in ["60+", "180+", "300+"]):
                    category = "Blitz"
                elif any(rapid in tc for rapid in ["600+", "900+", "1800+"]):
                    category = "Rapid"
                else:
                    category = "Other"
            elif tc == "-":
                category = "Correspondence"
            else:
                category = "Other"
            
            stats = time_control_data[category]
            stats['games'] += 1
            stats['total_accuracy'] += ga.accuracy_percentage
            
            if self._is_win(ga.game):
                stats['wins'] += 1
        
        # Calculate averages
        for category, stats in time_control_data.items():
            stats['win_rate'] = stats['wins'] / stats['games']
            stats['avg_accuracy'] = stats['total_accuracy'] / stats['games']
            del stats['total_accuracy']
        
        return dict(time_control_data)
    
    def _analyze_recent_form(self, recent_games: List[GameAnalysis]) -> Dict[str, Any]:
        """Analyze recent performance trends"""
        if not recent_games:
            return {}
        
        wins = sum(1 for ga in recent_games if self._is_win(ga.game))
        total = len(recent_games)
        avg_accuracy = np.mean([ga.accuracy_percentage for ga in recent_games])
        avg_blunders = np.mean([ga.blunders for ga in recent_games])
        
        return {
            'games': total,
            'wins': wins,
            'win_rate': wins / total,
            'avg_accuracy': avg_accuracy,
            'avg_blunders_per_game': avg_blunders,
            'trend': 'improving' if avg_accuracy > 70 else 'declining' if avg_accuracy < 60 else 'stable'
        }
    
    def _identify_strengths_and_weaknesses(self, game_analyses: List[GameAnalysis]) -> Tuple[List[str], List[str]]:
        """Identify player strengths and areas for improvement"""
        strengths = []
        weaknesses = []
        
        if not game_analyses:
            return strengths, weaknesses
        
        # Calculate phase accuracies
        opening_acc = np.mean([ga.opening_accuracy for ga in game_analyses])
        middlegame_acc = np.mean([ga.middlegame_accuracy for ga in game_analyses])
        endgame_acc = np.mean([ga.endgame_accuracy for ga in game_analyses if ga.endgame_accuracy > 0])
        
        # Analyze by phase
        phases = [
            ("Opening", opening_acc),
            ("Middlegame", middlegame_acc),
            ("Endgame", endgame_acc)
        ]
        
        phases.sort(key=lambda x: x[1], reverse=True)
        
        # Top phase is a strength, bottom is weakness
        if phases[0][1] > 75:
            strengths.append(f"Strong {phases[0][0].lower()} play ({phases[0][1]:.1f}% accuracy)")
        
        if phases[-1][1] < 65:
            weaknesses.append(f"Weak {phases[-1][0].lower()} play ({phases[-1][1]:.1f}% accuracy)")
        
        # Blunder rate analysis
        avg_blunders = np.mean([ga.blunders for ga in game_analyses])
        if avg_blunders < 0.5:
            strengths.append("Low blunder rate")
        elif avg_blunders > 2:
            weaknesses.append("High blunder rate")
        
        # Time management
        time_trouble_rate = np.mean([ga.time_trouble_moves / len(ga.move_analyses) for ga in game_analyses])
        if time_trouble_rate > 0.3:
            weaknesses.append("Frequent time trouble")
        
        return strengths, weaknesses
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics structure"""
        return PerformanceMetrics(
            total_games=0, wins=0, losses=0, draws=0, win_rate=0.0,
            total_moves=0, average_centipawn_loss=0.0, accuracy_percentage=0.0,
            blunder_rate=0.0, mistake_rate=0.0, inaccuracy_rate=0.0,
            average_move_time=None, time_pressure_performance=None,
            opening_stats={}, rating_progression=[], current_rating=None,
            rating_change=None, performance_by_rating_range={},
            performance_by_time_control={}, recent_form={},
            improvement_areas=[], strengths=[]
        )