"""
Actionable Insights Generator

Transforms performance analysis into specific, actionable recommendations
for chess improvement including:
- Opening repertoire suggestions
- Time control optimization
- Tactical training focus areas
- Blunder pattern identification
- Study recommendations
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
from collections import Counter

from analyzers.performance_calculator import PerformanceMetrics, GameAnalysis
from parsers.pgn_parser import ParsedGame

@dataclass
class TrainingRecommendation:
    """A specific training recommendation"""
    category: str  # "Opening", "Tactics", "Endgame", "Time Management", etc.
    priority: int  # 1-5, higher is more important
    title: str
    description: str
    specific_actions: List[str]
    expected_impact: str  # "High", "Medium", "Low"
    time_investment: str  # "15 min/day", "30 min/week", etc.

@dataclass
class GameSelection:
    """Recommended games for tonight"""
    time_controls: List[str]
    opening_focus: List[str]
    strategic_reminders: List[str]
    avoid_patterns: List[str]

@dataclass 
class ActionableInsights:
    """Complete set of actionable insights"""
    # Immediate actions for tonight
    tonight_strategy: GameSelection
    
    # Training recommendations by priority
    training_recommendations: List[TrainingRecommendation]
    
    # Quick wins (high impact, low effort)
    quick_wins: List[str]
    
    # Long-term development areas
    long_term_goals: List[str]
    
    # Pattern recognition
    recurring_mistakes: List[str]
    successful_patterns: List[str]
    
    # Performance optimization
    optimal_conditions: Dict[str, Any]

class InsightsGenerator:
    """Generate actionable insights from performance analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_insights(self, 
                         metrics: PerformanceMetrics,
                         game_analyses: List[GameAnalysis]) -> ActionableInsights:
        """Generate comprehensive actionable insights"""
        
        self.logger.info("Generating actionable insights...")
        
        # Generate tonight's strategy
        tonight_strategy = self._generate_tonight_strategy(metrics, game_analyses)
        
        # Generate training recommendations
        training_recs = self._generate_training_recommendations(metrics, game_analyses)
        
        # Identify quick wins
        quick_wins = self._identify_quick_wins(metrics, game_analyses)
        
        # Set long-term goals
        long_term_goals = self._set_long_term_goals(metrics)
        
        # Analyze patterns
        recurring_mistakes = self._identify_recurring_mistakes(game_analyses)
        successful_patterns = self._identify_successful_patterns(game_analyses)
        
        # Optimize conditions
        optimal_conditions = self._identify_optimal_conditions(metrics)
        
        return ActionableInsights(
            tonight_strategy=tonight_strategy,
            training_recommendations=training_recs,
            quick_wins=quick_wins,
            long_term_goals=long_term_goals,
            recurring_mistakes=recurring_mistakes,
            successful_patterns=successful_patterns,
            optimal_conditions=optimal_conditions
        )
    
    def _generate_tonight_strategy(self, 
                                  metrics: PerformanceMetrics,
                                  game_analyses: List[GameAnalysis]) -> GameSelection:
        """Generate strategy recommendations for tonight's games"""
        
        # Analyze best time controls
        best_time_controls = []
        for tc, stats in metrics.performance_by_time_control.items():
            if stats['games'] >= 5 and stats['win_rate'] > 0.4:  # Minimum sample size and reasonable performance
                best_time_controls.append(f"{tc} (Win rate: {stats['win_rate']:.1%})")
        
        if not best_time_controls:
            best_time_controls = ["Blitz (3+2) - Good for tactical practice"]
        
        # Identify best openings
        opening_focus = []
        for opening, stats in metrics.opening_stats.items():
            if stats['games'] >= 3 and stats['win_rate'] > 0.5:
                opening_focus.append(f"{opening[:30]}... (Win rate: {stats['win_rate']:.1%})")
        
        if not opening_focus:
            opening_focus = ["Stick to familiar openings", "Focus on solid development"]
        
        # Strategic reminders based on weaknesses
        strategic_reminders = []
        
        if metrics.blunder_rate > 0.1:  # More than 10% blunder rate
            strategic_reminders.append("Take extra time on tactical positions")
            strategic_reminders.append("Double-check forcing moves")
        
        if metrics.average_move_time and metrics.average_move_time < 10:
            strategic_reminders.append("Slow down - you're playing too fast")
        
        if "time trouble" in [area.lower() for area in metrics.improvement_areas]:
            strategic_reminders.append("Manage time better - aim for 15+ seconds per move")
        
        # Phase-specific reminders
        recent_games = game_analyses[-10:] if len(game_analyses) >= 10 else game_analyses
        if recent_games:
            avg_opening_acc = np.mean([ga.opening_accuracy for ga in recent_games])
            avg_endgame_acc = np.mean([ga.endgame_accuracy for ga in recent_games if ga.endgame_accuracy > 0])
            
            if avg_opening_acc < 70:
                strategic_reminders.append("Focus on opening principles: development, king safety, center control")
            
            if avg_endgame_acc < 65:
                strategic_reminders.append("Be extra careful in endgames - accuracy drops here")
        
        if not strategic_reminders:
            strategic_reminders = ["Play your usual style", "Trust your preparation"]
        
        # Patterns to avoid
        avoid_patterns = self._identify_tonight_avoidance_patterns(game_analyses)
        
        return GameSelection(
            time_controls=best_time_controls[:3],  # Top 3
            opening_focus=opening_focus[:3],
            strategic_reminders=strategic_reminders,
            avoid_patterns=avoid_patterns
        )
    
    def _identify_tonight_avoidance_patterns(self, game_analyses: List[GameAnalysis]) -> List[str]:
        """Identify patterns to avoid tonight based on recent losses"""
        avoid_patterns = []
        
        # Look at recent losses
        recent_losses = []
        for ga in game_analyses[-20:]:  # Last 20 games
            if not self._is_win(ga.game) and not self._is_draw(ga.game):
                recent_losses.append(ga)
        
        if not recent_losses:
            return ["Avoid time pressure", "Don't rush in complex positions"]
        
        # Analyze common patterns in losses
        high_blunder_losses = [ga for ga in recent_losses if ga.blunders >= 2]
        if len(high_blunder_losses) > len(recent_losses) * 0.3:
            avoid_patterns.append("Avoid tactical complications when tired")
        
        time_trouble_losses = [ga for ga in recent_losses if ga.time_trouble_moves > 5]
        if len(time_trouble_losses) > len(recent_losses) * 0.3:
            avoid_patterns.append("Don't get into severe time trouble")
        
        # Check for opening-related losses
        opening_losses = {}
        for ga in recent_losses:
            if ga.game.metadata.eco:
                eco = ga.game.metadata.eco
                opening_losses[eco] = opening_losses.get(eco, 0) + 1
        
        if opening_losses:
            worst_opening = max(opening_losses.items(), key=lambda x: x[1])
            if worst_opening[1] >= 2:
                avoid_patterns.append(f"Avoid {worst_opening[0]} opening tonight")
        
        if not avoid_patterns:
            avoid_patterns = ["Avoid time pressure", "Double-check tactics"]
        
        return avoid_patterns
    
    def _generate_training_recommendations(self, 
                                         metrics: PerformanceMetrics,
                                         game_analyses: List[GameAnalysis]) -> List[TrainingRecommendation]:
        """Generate prioritized training recommendations"""
        
        recommendations = []
        
        # Tactical training (high priority if blunder rate is high)
        if metrics.blunder_rate > 0.08:  # More than 8% blunder rate
            recommendations.append(TrainingRecommendation(
                category="Tactics",
                priority=5,
                title="Intensive Tactical Training",
                description=f"Your blunder rate is {metrics.blunder_rate:.1%}, which is above optimal. Focus on tactical pattern recognition.",
                specific_actions=[
                    "Solve 15-20 tactical puzzles daily on Lichess/Chess.com",
                    "Practice 'checks, captures, threats' in every position",
                    "Study common tactical motifs: pins, forks, discovered attacks",
                    "Review your recent blunders and identify the tactical themes"
                ],
                expected_impact="High",
                time_investment="20-30 min/day"
            ))
        
        # Opening recommendations based on performance
        opening_recs = self._generate_opening_recommendations(metrics)
        if opening_recs:
            recommendations.extend(opening_recs)
        
        # Time management training
        if "time trouble" in [area.lower() for area in metrics.improvement_areas]:
            recommendations.append(TrainingRecommendation(
                category="Time Management",
                priority=4,
                title="Time Management Improvement",
                description="You frequently get into time trouble, which hurts your performance.",
                specific_actions=[
                    "Practice with shorter time controls to build speed",
                    "Learn to recognize when to play fast vs. slow",
                    "Set time budgets: spend more time on critical positions",
                    "Practice endgames to play final moves quickly and accurately"
                ],
                expected_impact="High",
                time_investment="Incorporate into regular play"
            ))
        
        # Phase-specific training
        phase_recs = self._generate_phase_recommendations(game_analyses)
        recommendations.extend(phase_recs)
        
        # Calculation training
        if metrics.mistake_rate > 0.15:  # More than 15% mistake rate
            recommendations.append(TrainingRecommendation(
                category="Calculation",
                priority=3,
                title="Improve Calculation Skills",
                description="You're making too many mistakes, indicating calculation issues.",
                specific_actions=[
                    "Practice calculating 3-4 moves ahead consistently",
                    "Use the 'candidate moves' method: identify all reasonable moves first",
                    "Practice visualization exercises",
                    "Study master games focusing on their thought process"
                ],
                expected_impact="Medium",
                time_investment="15 min/day"
            ))
        
        # Sort by priority
        recommendations.sort(key=lambda x: x.priority, reverse=True)
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _generate_opening_recommendations(self, metrics: PerformanceMetrics) -> List[TrainingRecommendation]:
        """Generate opening-specific recommendations"""
        recommendations = []
        
        if not metrics.opening_stats:
            return recommendations
        
        # Find best and worst performing openings
        opening_performance = []
        for opening, stats in metrics.opening_stats.items():
            if stats['games'] >= 3:  # Minimum sample size
                score = stats['win_rate'] * 0.7 + (stats['avg_accuracy'] / 100) * 0.3
                opening_performance.append((opening, stats, score))
        
        if not opening_performance:
            return recommendations
        
        opening_performance.sort(key=lambda x: x[2])
        
        # Recommend expanding best openings
        best_openings = opening_performance[-2:]  # Top 2
        if best_openings:
            best_opening = best_openings[-1]
            recommendations.append(TrainingRecommendation(
                category="Opening",
                priority=3,
                title=f"Expand Your Best Opening",
                description=f"You perform well in {best_opening[0][:30]}... (Win rate: {best_opening[1]['win_rate']:.1%}). Deepen your knowledge.",
                specific_actions=[
                    f"Study 5-10 master games in this opening",
                    "Learn the main theoretical lines and typical plans",
                    "Practice this opening in your next 10 games",
                    "Understand the typical pawn structures and piece play"
                ],
                expected_impact="Medium",
                time_investment="2-3 hours total study"
            ))
        
        # Address worst performing opening
        worst_openings = opening_performance[:2]  # Bottom 2
        if worst_openings and worst_openings[0][2] < 0.4:  # Poor performance
            worst_opening = worst_openings[0]
            recommendations.append(TrainingRecommendation(
                category="Opening",
                priority=2,
                title=f"Fix Problematic Opening",
                description=f"You struggle with {worst_opening[0][:30]}... (Win rate: {worst_opening[1]['win_rate']:.1%}). Consider switching or improving.",
                specific_actions=[
                    "Either avoid this opening or study it intensively",
                    "Learn a solid alternative opening system",
                    "Understand why you're struggling: tactical issues? positional?",
                    "Practice with a stronger player who knows this opening"
                ],
                expected_impact="Medium",
                time_investment="1-2 hours study or practice alternative"
            ))
        
        return recommendations
    
    def _generate_phase_recommendations(self, game_analyses: List[GameAnalysis]) -> List[TrainingRecommendation]:
        """Generate phase-specific training recommendations"""
        recommendations = []
        
        if not game_analyses:
            return recommendations
        
        # Calculate phase accuracies
        opening_acc = np.mean([ga.opening_accuracy for ga in game_analyses])
        middlegame_acc = np.mean([ga.middlegame_accuracy for ga in game_analyses])
        endgame_acc = np.mean([ga.endgame_accuracy for ga in game_analyses if ga.endgame_accuracy > 0])
        
        # Opening recommendations
        if opening_acc < 70:
            recommendations.append(TrainingRecommendation(
                category="Opening",
                priority=4,
                title="Improve Opening Play",
                description=f"Your opening accuracy is {opening_acc:.1f}%, indicating room for improvement in the first 10 moves.",
                specific_actions=[
                    "Study opening principles: development, king safety, center control",
                    "Learn 2-3 solid opening systems rather than many openings",
                    "Practice common opening tactics and traps",
                    "Watch educational videos on opening concepts"
                ],
                expected_impact="High",
                time_investment="1 hour/week"
            ))
        
        # Middlegame recommendations  
        if middlegame_acc < 65:
            recommendations.append(TrainingRecommendation(
                category="Middlegame",
                priority=4,
                title="Strengthen Middlegame Understanding",
                description=f"Your middlegame accuracy is {middlegame_acc:.1f}%. This is where most games are decided.",
                specific_actions=[
                    "Study typical middlegame plans and pawn structures",
                    "Practice piece coordination and activity",
                    "Learn to evaluate positions: space, piece activity, king safety",
                    "Study annotated master games focusing on middlegame plans"
                ],
                expected_impact="High",
                time_investment="2 hours/week"
            ))
        
        # Endgame recommendations
        if endgame_acc < 60 and endgame_acc > 0:
            recommendations.append(TrainingRecommendation(
                category="Endgame",
                priority=3,
                title="Essential Endgame Study",
                description=f"Your endgame accuracy is {endgame_acc:.1f}%. Endgames are very important for rating improvement.",
                specific_actions=[
                    "Learn basic checkmate patterns: Q+K vs K, R+K vs K",
                    "Study key pawn endgames: opposition, passed pawns",
                    "Practice basic piece endgames: R vs R, B vs N",
                    "Use endgame training tools like Lichess endgame practice"
                ],
                expected_impact="Medium",
                time_investment="30 min/week"
            ))
        
        return recommendations
    
    def _identify_quick_wins(self, 
                           metrics: PerformanceMetrics,
                           game_analyses: List[GameAnalysis]) -> List[str]:
        """Identify high-impact, low-effort improvements"""
        quick_wins = []
        
        # Blunder reduction
        if metrics.blunder_rate > 0.05:
            quick_wins.append("Before making any forcing move (check, capture, threat), count to 3 and double-check")
        
        # Time management
        if metrics.average_move_time and metrics.average_move_time < 8:
            quick_wins.append("Slow down! Aim for at least 10 seconds per move in rapid games")
        
        # Opening quick wins
        if metrics.opening_stats:
            best_opening = max(metrics.opening_stats.items(), 
                             key=lambda x: x[1]['win_rate'] if x[1]['games'] >= 3 else 0)
            if best_opening[1]['games'] >= 3:
                quick_wins.append(f"Play your best opening more often: {best_opening[0][:30]}...")
        
        # Simple tactical awareness
        if metrics.mistake_rate > 0.1:
            quick_wins.append("Before each move, ask: 'What is my opponent threatening?'")
        
        # Time control optimization
        best_tc = None
        best_performance = 0
        for tc, stats in metrics.performance_by_time_control.items():
            if stats['games'] >= 5:
                score = stats['win_rate'] * 0.6 + (stats['avg_accuracy'] / 100) * 0.4
                if score > best_performance:
                    best_performance = score
                    best_tc = tc
        
        if best_tc:
            quick_wins.append(f"Focus on {best_tc} time controls where you perform best")
        
        return quick_wins[:5]  # Top 5 quick wins
    
    def _set_long_term_goals(self, metrics: PerformanceMetrics) -> List[str]:
        """Set long-term development goals"""
        goals = []
        
        # Rating goals
        if metrics.current_rating:
            if metrics.current_rating < 1400:
                goals.append("Reach 1400 rating by improving tactical awareness and reducing blunders")
            elif metrics.current_rating < 1600:
                goals.append("Reach 1600 rating by developing positional understanding")
            elif metrics.current_rating < 1800:
                goals.append("Reach 1800 rating by mastering key endgames and opening preparation")
        
        # Accuracy goals
        if metrics.accuracy_percentage < 80:
            goals.append("Achieve 80%+ average accuracy through better calculation")
        
        # Blunder reduction goals
        if metrics.blunder_rate > 0.05:
            goals.append("Reduce blunder rate below 5% through consistent tactical training")
        
        # Opening repertoire goals
        goals.append("Develop a solid opening repertoire with 2-3 systems for each color")
        
        # Study goals
        goals.append("Study 100 annotated master games over the next 6 months")
        
        return goals[:4]  # Top 4 goals
    
    def _identify_recurring_mistakes(self, game_analyses: List[GameAnalysis]) -> List[str]:
        """Identify recurring mistake patterns"""
        mistakes = []
        
        if not game_analyses:
            return mistakes
        
        # Analyze blunder frequency by game phase
        opening_blunders = sum(1 for ga in game_analyses for ma in ga.move_analyses[:10] if ma.is_blunder)
        middlegame_blunders = sum(1 for ga in game_analyses for ma in ga.move_analyses[10:40] if ma.is_blunder)
        endgame_blunders = sum(1 for ga in game_analyses for ma in ga.move_analyses[40:] if ma.is_blunder)
        
        total_opening_moves = sum(min(10, len(ga.move_analyses)) for ga in game_analyses)
        total_middlegame_moves = sum(min(30, max(0, len(ga.move_analyses) - 10)) for ga in game_analyses)
        total_endgame_moves = sum(max(0, len(ga.move_analyses) - 40) for ga in game_analyses)
        
        if total_opening_moves > 0 and opening_blunders / total_opening_moves > 0.03:
            mistakes.append("Frequent opening blunders - review opening principles")
        
        if total_middlegame_moves > 0 and middlegame_blunders / total_middlegame_moves > 0.03:
            mistakes.append("Tactical mistakes in middlegame - improve pattern recognition")
        
        if total_endgame_moves > 0 and endgame_blunders / total_endgame_moves > 0.05:
            mistakes.append("Endgame conversion errors - study basic endgames")
        
        # Time trouble pattern
        time_trouble_rate = np.mean([ga.time_trouble_moves / len(ga.move_analyses) for ga in game_analyses])
        if time_trouble_rate > 0.25:
            mistakes.append("Frequent time trouble leads to poor moves")
        
        return mistakes[:3]  # Top 3 patterns
    
    def _identify_successful_patterns(self, game_analyses: List[GameAnalysis]) -> List[str]:
        """Identify successful patterns to reinforce"""
        patterns = []
        
        if not game_analyses:
            return patterns
        
        # Find games with high accuracy
        high_accuracy_games = [ga for ga in game_analyses if ga.accuracy_percentage > 85]
        
        if len(high_accuracy_games) > len(game_analyses) * 0.2:  # At least 20% high accuracy
            patterns.append("You play very accurately when you take your time - continue this approach")
        
        # Find successful openings
        win_games = [ga for ga in game_analyses if self._is_win(ga.game)]
        if win_games:
            win_openings = Counter([ga.game.metadata.eco for ga in win_games if ga.game.metadata.eco])
            if win_openings:
                best_opening = win_openings.most_common(1)[0]
                patterns.append(f"Strong performance in {best_opening[0]} - continue developing this opening")
        
        # Low blunder games
        low_blunder_games = [ga for ga in game_analyses if ga.blunders == 0]
        if len(low_blunder_games) > len(game_analyses) * 0.3:
            patterns.append("You avoid blunders well in most games - maintain this careful approach")
        
        return patterns[:3]  # Top 3 patterns
    
    def _identify_optimal_conditions(self, metrics: PerformanceMetrics) -> Dict[str, Any]:
        """Identify optimal playing conditions"""
        optimal = {}
        
        # Best time control
        if metrics.performance_by_time_control:
            best_tc = max(metrics.performance_by_time_control.items(),
                         key=lambda x: x[1]['win_rate'] if x[1]['games'] >= 5 else 0)
            if best_tc[1]['games'] >= 5:
                optimal['time_control'] = f"{best_tc[0]} (Win rate: {best_tc[1]['win_rate']:.1%})"
        
        # Best rating range to play against
        if metrics.performance_by_rating_range:
            best_rating = max(metrics.performance_by_rating_range.items(),
                            key=lambda x: x[1]['win_rate'] if x[1]['games'] >= 3 else 0)
            if best_rating[1]['games'] >= 3:
                optimal['opponent_rating'] = f"{best_rating[0]} (Win rate: {best_rating[1]['win_rate']:.1%})"
        
        # Performance trends
        if metrics.recent_form:
            optimal['recent_trend'] = metrics.recent_form.get('trend', 'stable')
        
        return optimal
    
    def _is_win(self, game: ParsedGame) -> bool:
        """Check if game was a win"""
        if game.player_color == "white":
            return game.metadata.result == "1-0"
        else:
            return game.metadata.result == "0-1"
    
    def _is_draw(self, game: ParsedGame) -> bool:
        """Check if game was a draw"""
        return game.metadata.result == "1/2-1/2"