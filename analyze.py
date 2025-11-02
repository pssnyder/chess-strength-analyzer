"""
Chess Strength Analyzer - Main Analysis Engine

Comprehensive chess performance analysis with actionable insights.
Processes PGN files to generate detailed performance metrics and 
specific recommendations for improvement.
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional
import argparse
import json
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from parsers.pgn_parser import PGNParser, GameFilter
from analyzers.stockfish_analyzer import StockfishAnalyzer
from analyzers.performance_calculator import PerformanceCalculator
from insights.insights_generator import InsightsGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analysis.log'),
        logging.StreamHandler()
    ]
)

class ChessAnalyzer:
    """Main chess analysis orchestrator"""
    
    def __init__(self, 
                 player_name: str = "v7p3r",
                 stockfish_path: Optional[str] = None,
                 stockfish_depth: int = 12):
        """
        Initialize the chess analyzer
        
        Args:
            player_name: Name of the player to analyze
            stockfish_path: Path to Stockfish executable
            stockfish_depth: Analysis depth for Stockfish
        """
        self.player_name = player_name
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.parser = PGNParser(player_name)
        
        # Use provided Stockfish path or find automatically
        if not stockfish_path:
            stockfish_path = "S:\\Maker Stuff\\Programming\\Chess Engines\\Chess Engine Playground\\engine-tester\\engines\\Stockfish\\stockfish-windows-x86-64-avx2.exe"
        
        self.analyzer = StockfishAnalyzer(
            stockfish_path=stockfish_path,
            depth=stockfish_depth
        )
        
        self.calculator = PerformanceCalculator()
        self.insights_generator = InsightsGenerator()
        
        self.logger.info(f"Chess Analyzer initialized for player: {player_name}")
    
    def analyze_directory(self, 
                         data_dir: Path,
                         max_games: Optional[int] = None,
                         quick_analysis: bool = False) -> dict:
        """
        Analyze all PGN files in a directory
        
        Args:
            data_dir: Directory containing PGN files
            max_games: Maximum number of games to analyze (None for all)
            quick_analysis: If True, use faster analysis with fewer games
        
        Returns:
            Complete analysis results dictionary
        """
        self.logger.info(f"Starting analysis of directory: {data_dir}")
        
        # Parse all PGN files
        all_games = []
        pgn_files = list(data_dir.glob("*.pgn"))
        
        self.logger.info(f"Found {len(pgn_files)} PGN files")
        
        for pgn_file in pgn_files:
            self.logger.info(f"Parsing {pgn_file.name}...")
            games = self.parser.parse_file(pgn_file)
            all_games.extend(games)
        
        self.logger.info(f"Parsed {len(all_games)} total games")
        
        # Filter to player games only
        player_games = GameFilter.filter_by_player(all_games, self.player_name)
        self.logger.info(f"Found {len(player_games)} games where {self.player_name} played")
        
        if not player_games:
            self.logger.error("No games found for the specified player")
            return {}
        
        # Sort by date
        player_games.sort(key=lambda g: g.metadata.date)
        
        # Limit games if requested
        if max_games:
            player_games = player_games[-max_games:]  # Take most recent games
            self.logger.info(f"Limited analysis to {len(player_games)} most recent games")
        
        if quick_analysis:
            # For quick analysis, take every 3rd game or max 30 games
            step = max(1, len(player_games) // 30)
            player_games = player_games[::step][:30]
            self.logger.info(f"Quick analysis: analyzing {len(player_games)} games")
        
        # Analyze games
        self.logger.info("Starting Stockfish analysis...")
        game_analyses = self.calculator.analyze_games_batch(
            player_games, 
            self.analyzer,
            max_games=None if not quick_analysis else 30
        )
        
        if not game_analyses:
            self.logger.error("No games could be analyzed")
            return {}
        
        self.logger.info(f"Successfully analyzed {len(game_analyses)} games")
        
        # Calculate comprehensive metrics
        self.logger.info("Calculating performance metrics...")
        metrics = self.calculator.calculate_comprehensive_metrics(game_analyses)
        
        # Generate actionable insights
        self.logger.info("Generating actionable insights...")
        insights = self.insights_generator.generate_insights(metrics, game_analyses)
        
        # Compile results
        results = {
            'analysis_info': {
                'player_name': self.player_name,
                'total_games_parsed': len(all_games),
                'player_games_found': len(player_games),
                'games_analyzed': len(game_analyses),
                'analysis_date': datetime.now().isoformat(),
                'quick_analysis': quick_analysis
            },
            'performance_metrics': self._metrics_to_dict(metrics),
            'actionable_insights': self._insights_to_dict(insights),
            'recent_games_summary': self._summarize_recent_games(game_analyses[-10:])
        }
        
        self.logger.info("Analysis completed successfully!")
        return results
    
    def analyze_single_file(self, pgn_file: Path, max_games: Optional[int] = None) -> dict:
        """Analyze a single PGN file"""
        return self.analyze_directory(pgn_file.parent, max_games)
    
    def _metrics_to_dict(self, metrics) -> dict:
        """Convert performance metrics to dictionary"""
        return {
            'overall_performance': {
                'total_games': metrics.total_games,
                'wins': metrics.wins,
                'losses': metrics.losses,
                'draws': metrics.draws,
                'win_rate': f"{metrics.win_rate:.1%}",
                'current_rating': metrics.current_rating,
                'rating_change': metrics.rating_change
            },
            'move_quality': {
                'total_moves_analyzed': metrics.total_moves,
                'average_accuracy': f"{metrics.accuracy_percentage:.1f}%",
                'average_centipawn_loss': f"{metrics.average_centipawn_loss:.1f}",
                'blunder_rate': f"{metrics.blunder_rate:.1%}",
                'mistake_rate': f"{metrics.mistake_rate:.1%}",
                'inaccuracy_rate': f"{metrics.inaccuracy_rate:.1%}"
            },
            'time_management': {
                'average_move_time': f"{metrics.average_move_time:.1f}s" if metrics.average_move_time else "N/A"
            },
            'opening_performance': self._format_opening_stats(metrics.opening_stats),
            'performance_by_time_control': self._format_time_control_stats(metrics.performance_by_time_control),
            'performance_by_rating': self._format_rating_stats(metrics.performance_by_rating_range),
            'recent_form': metrics.recent_form,
            'strengths': metrics.strengths,
            'improvement_areas': metrics.improvement_areas
        }
    
    def _insights_to_dict(self, insights) -> dict:
        """Convert insights to dictionary"""
        return {
            'tonight_strategy': {
                'recommended_time_controls': insights.tonight_strategy.time_controls,
                'opening_focus': insights.tonight_strategy.opening_focus,
                'strategic_reminders': insights.tonight_strategy.strategic_reminders,
                'avoid_patterns': insights.tonight_strategy.avoid_patterns
            },
            'training_recommendations': [
                {
                    'category': rec.category,
                    'priority': rec.priority,
                    'title': rec.title,
                    'description': rec.description,
                    'actions': rec.specific_actions,
                    'expected_impact': rec.expected_impact,
                    'time_investment': rec.time_investment
                }
                for rec in insights.training_recommendations
            ],
            'quick_wins': insights.quick_wins,
            'long_term_goals': insights.long_term_goals,
            'recurring_mistakes': insights.recurring_mistakes,
            'successful_patterns': insights.successful_patterns,
            'optimal_conditions': insights.optimal_conditions
        }
    
    def _format_opening_stats(self, opening_stats: dict) -> dict:
        """Format opening statistics for display"""
        formatted = {}
        for opening, stats in opening_stats.items():
            if stats['games'] >= 2:  # Only show openings with multiple games
                formatted[opening] = {
                    'games': stats['games'],
                    'win_rate': f"{stats['win_rate']:.1%}",
                    'average_accuracy': f"{stats['avg_accuracy']:.1f}%"
                }
        return formatted
    
    def _format_time_control_stats(self, tc_stats: dict) -> dict:
        """Format time control statistics"""
        formatted = {}
        for tc, stats in tc_stats.items():
            formatted[tc] = {
                'games': stats['games'],
                'win_rate': f"{stats['win_rate']:.1%}",
                'average_accuracy': f"{stats['avg_accuracy']:.1f}%"
            }
        return formatted
    
    def _format_rating_stats(self, rating_stats: dict) -> dict:
        """Format rating-based statistics"""
        formatted = {}
        for rating_range, stats in rating_stats.items():
            formatted[rating_range] = {
                'games': stats['games'],
                'win_rate': f"{stats['win_rate']:.1%}",
                'average_accuracy': f"{stats['avg_accuracy']:.1f}%"
            }
        return formatted
    
    def _summarize_recent_games(self, recent_games) -> dict:
        """Summarize recent games performance"""
        if not recent_games:
            return {}
        
        wins = sum(1 for ga in recent_games if self._is_win(ga.game))
        avg_accuracy = sum(ga.accuracy_percentage for ga in recent_games) / len(recent_games)
        avg_blunders = sum(ga.blunders for ga in recent_games) / len(recent_games)
        
        return {
            'games_count': len(recent_games),
            'wins': wins,
            'win_rate': f"{wins/len(recent_games):.1%}",
            'average_accuracy': f"{avg_accuracy:.1f}%",
            'average_blunders_per_game': f"{avg_blunders:.1f}",
            'trend': 'improving' if avg_accuracy > 70 else 'needs_work'
        }
    
    def _is_win(self, game) -> bool:
        """Check if game was a win"""
        if game.player_color == "white":
            return game.metadata.result == "1-0"
        else:
            return game.metadata.result == "0-1"
    
    def save_results(self, results: dict, output_file: Path):
        """Save analysis results to JSON file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Results saved to {output_file}")

def print_insights_summary(results: dict):
    """Print a summary of insights to console"""
    insights = results.get('actionable_insights', {})
    metrics = results.get('performance_metrics', {})
    
    print("\n" + "="*60)
    print("🏆 CHESS STRENGTH ANALYSIS SUMMARY")
    print("="*60)
    
    # Overall performance
    overall = metrics.get('overall_performance', {})
    print(f"\n📊 Overall Performance:")
    print(f"   Games: {overall.get('total_games', 0)} | Win Rate: {overall.get('win_rate', 'N/A')}")
    print(f"   Current Rating: {overall.get('current_rating', 'Unknown')}")
    
    # Move quality
    quality = metrics.get('move_quality', {})
    print(f"\n🎯 Move Quality:")
    print(f"   Accuracy: {quality.get('average_accuracy', 'N/A')}")
    print(f"   Blunder Rate: {quality.get('blunder_rate', 'N/A')}")
    
    # Tonight's strategy
    tonight = insights.get('tonight_strategy', {})
    print(f"\n🌙 TONIGHT'S GAME STRATEGY:")
    
    time_controls = tonight.get('recommended_time_controls', [])
    if time_controls:
        print(f"   🕒 Best Time Controls:")
        for tc in time_controls[:2]:
            print(f"      • {tc}")
    
    reminders = tonight.get('strategic_reminders', [])
    if reminders:
        print(f"   📝 Key Reminders:")
        for reminder in reminders[:3]:
            print(f"      • {reminder}")
    
    avoid = tonight.get('avoid_patterns', [])
    if avoid:
        print(f"   ⚠️  Avoid Tonight:")
        for pattern in avoid[:2]:
            print(f"      • {pattern}")
    
    # Quick wins
    quick_wins = insights.get('quick_wins', [])
    if quick_wins:
        print(f"\n⚡ QUICK WINS (Immediate Improvements):")
        for win in quick_wins[:3]:
            print(f"   • {win}")
    
    # Top training recommendations
    training = insights.get('training_recommendations', [])
    if training:
        print(f"\n📚 TOP TRAINING PRIORITIES:")
        for i, rec in enumerate(training[:2]):
            print(f"   {i+1}. {rec['title']} ({rec['category']})")
            print(f"      {rec['description']}")
            if rec.get('actions'):
                print(f"      Action: {rec['actions'][0]}")
    
    # Strengths and weaknesses
    strengths = metrics.get('strengths', [])
    weaknesses = metrics.get('improvement_areas', [])
    
    if strengths:
        print(f"\n💪 Your Strengths:")
        for strength in strengths[:2]:
            print(f"   • {strength}")
    
    if weaknesses:
        print(f"\n🎯 Focus Areas:")
        for weakness in weaknesses[:2]:
            print(f"   • {weakness}")
    
    print("\n" + "="*60)
    print("Good luck in your games tonight! 🎲♟️")
    print("="*60)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Chess Strength Analyzer")
    parser.add_argument("--data-dir", type=str, default="data", 
                       help="Directory containing PGN files")
    parser.add_argument("--player", type=str, default="v7p3r",
                       help="Player name to analyze")
    parser.add_argument("--max-games", type=int, default=None,
                       help="Maximum number of games to analyze")
    parser.add_argument("--quick", action="store_true",
                       help="Quick analysis mode (faster, fewer games)")
    parser.add_argument("--output", type=str, default="analysis_results.json",
                       help="Output file for results")
    parser.add_argument("--stockfish-path", type=str, default=None,
                       help="Path to Stockfish executable")
    
    args = parser.parse_args()
    
    try:
        # Initialize analyzer
        analyzer = ChessAnalyzer(
            player_name=args.player,
            stockfish_path=args.stockfish_path
        )
        
        # Run analysis
        data_dir = Path(args.data_dir)
        if not data_dir.exists():
            print(f"Error: Data directory {data_dir} does not exist")
            return 1
        
        results = analyzer.analyze_directory(
            data_dir=data_dir,
            max_games=args.max_games,
            quick_analysis=args.quick
        )
        
        if not results:
            print("Error: Analysis failed to produce results")
            return 1
        
        # Save results
        output_file = Path(args.output)
        analyzer.save_results(results, output_file)
        
        # Print summary
        print_insights_summary(results)
        
        print(f"\n📁 Full results saved to: {output_file}")
        print("🌐 Run 'python web_dashboard.py' to view detailed analysis in browser")
        
        return 0
        
    except Exception as e:
        logging.error(f"Analysis failed: {e}")
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())