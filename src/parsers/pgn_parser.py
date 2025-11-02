"""
PGN Parser for Chess Strength Analyzer

Handles parsing of PGN files from various sources including:
- Lichess exports
- Chess.com exports  
- Engine vs engine games
- Local tournament data

Extracts game metadata, moves, timing information, and normalizes data structure.
"""

import chess.pgn
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import logging

@dataclass
class GameMetadata:
    """Standardized game metadata structure"""
    event: str
    site: str
    date: datetime
    round: Optional[str]
    white: str
    black: str
    result: str
    white_elo: Optional[int]
    black_elo: Optional[int]
    time_control: Optional[str]
    eco: Optional[str]
    opening: Optional[str]
    termination: Optional[str]
    game_id: Optional[str]
    variant: str = "Standard"

@dataclass
class MoveData:
    """Individual move information"""
    move_number: int
    color: str  # 'white' or 'black'
    san: str  # Standard Algebraic Notation
    uci: str  # Universal Chess Interface notation
    clock_time: Optional[float] = None  # Remaining time in seconds
    move_time: Optional[float] = None   # Time spent on this move

@dataclass 
class ParsedGame:
    """Complete parsed game data"""
    metadata: GameMetadata
    moves: List[MoveData]
    final_position: str  # FEN notation
    raw_pgn: str
    player_color: Optional[str] = None  # Color of the player being analyzed

class PGNParser:
    """Robust PGN parser handling multiple formats"""
    
    def __init__(self, player_name: str = "v7p3r"):
        self.player_name = player_name
        self.logger = logging.getLogger(__name__)
        
    def parse_file(self, file_path: Path) -> List[ParsedGame]:
        """Parse all games from a PGN file"""
        games = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as pgn_file:
                while True:
                    game = chess.pgn.read_game(pgn_file)
                    if game is None:
                        break
                    
                    parsed_game = self._parse_game(game)
                    if parsed_game:
                        games.append(parsed_game)
                        
        except Exception as e:
            self.logger.error(f"Error parsing file {file_path}: {e}")
            
        return games
    
    def _parse_game(self, game: chess.pgn.Game) -> Optional[ParsedGame]:
        """Parse a single game object"""
        try:
            # Extract metadata
            metadata = self._extract_metadata(game.headers)
            
            # Determine player color
            player_color = None
            if self.player_name.lower() in metadata.white.lower():
                player_color = "white"
            elif self.player_name.lower() in metadata.black.lower():
                player_color = "black"
            
            # Extract moves with timing
            moves = self._extract_moves(game)
            
            # Get final position
            board = game.board()
            for move in game.mainline_moves():
                board.push(move)
            final_position = board.fen()
            
            return ParsedGame(
                metadata=metadata,
                moves=moves,
                final_position=final_position,
                raw_pgn=str(game),
                player_color=player_color
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing game: {e}")
            return None
    
    def _extract_metadata(self, headers) -> GameMetadata:
        """Extract and normalize game metadata"""
        
        # Parse date
        date_str = headers.get('Date', '????.??.??')
        try:
            if date_str != '????.??.??':
                date = datetime.strptime(date_str, '%Y.%m.%d')
            else:
                date = datetime.now()  # Fallback
        except ValueError:
            date = datetime.now()
        
        # Parse ELO ratings
        white_elo = self._parse_elo(headers.get('WhiteElo'))
        black_elo = self._parse_elo(headers.get('BlackElo'))
        
        return GameMetadata(
            event=headers.get('Event', 'Unknown'),
            site=headers.get('Site', 'Unknown'),
            date=date,
            round=headers.get('Round'),
            white=headers.get('White', 'Unknown'),
            black=headers.get('Black', 'Unknown'), 
            result=headers.get('Result', '*'),
            white_elo=white_elo,
            black_elo=black_elo,
            time_control=headers.get('TimeControl'),
            eco=headers.get('ECO'),
            opening=headers.get('Opening'),
            termination=headers.get('Termination'),
            game_id=headers.get('GameId') or headers.get('Site', '').split('/')[-1],
            variant=headers.get('Variant', 'Standard')
        )
    
    def _parse_elo(self, elo_str: Optional[str]) -> Optional[int]:
        """Parse ELO rating from string"""
        if not elo_str or elo_str == '?':
            return None
        try:
            return int(elo_str)
        except ValueError:
            return None
    
    def _extract_moves(self, game: chess.pgn.Game) -> List[MoveData]:
        """Extract moves with timing information"""
        moves = []
        board = game.board()
        move_number = 1
        
        try:
            for node in game.mainline():
                if node.move:
                    try:
                        # Verify move is legal before processing
                        if node.move not in board.legal_moves:
                            self.logger.warning(f"Illegal move detected: {node.move} in position {board.fen()}")
                            continue
                            
                        color = "white" if board.turn == chess.WHITE else "black"
                        
                        # Extract timing information
                        clock_time = self._extract_clock_time(node.comment)
                        
                        # Get SAN before making the move
                        try:
                            san = board.san(node.move)
                        except Exception as e:
                            self.logger.warning(f"Error getting SAN for move {node.move}: {e}")
                            san = str(node.move)  # Fallback to UCI
                        
                        move_data = MoveData(
                            move_number=move_number if color == "white" else move_number,
                            color=color,
                            san=san,
                            uci=node.move.uci(),
                            clock_time=clock_time
                        )
                        
                        moves.append(move_data)
                        board.push(node.move)
                        
                        if color == "black":
                            move_number += 1
                            
                    except Exception as e:
                        self.logger.warning(f"Error processing move {node.move}: {e}")
                        continue
                        
        except Exception as e:
            self.logger.error(f"Error extracting moves from game: {e}")
        
        # Calculate move times
        self._calculate_move_times(moves)
        
        return moves
    
    def _extract_clock_time(self, comment: str) -> Optional[float]:
        """Extract remaining clock time from move comment"""
        if not comment:
            return None
            
        # Look for [%clk H:MM:SS] format
        clk_match = re.search(r'\[%clk (\d+):(\d+):(\d+)\]', comment)
        if clk_match:
            hours, minutes, seconds = map(int, clk_match.groups())
            return hours * 3600 + minutes * 60 + seconds
        
        # Look for [%clk MM:SS] format
        clk_match = re.search(r'\[%clk (\d+):(\d+)\]', comment)
        if clk_match:
            minutes, seconds = map(int, clk_match.groups())
            return minutes * 60 + seconds
            
        return None
    
    def _calculate_move_times(self, moves: List[MoveData]):
        """Calculate time spent on each move"""
        prev_time_by_color: Dict[str, Optional[float]] = {"white": None, "black": None}
        
        for move in moves:
            prev_time = prev_time_by_color[move.color]
            if move.clock_time and prev_time is not None:
                move.move_time = prev_time - move.clock_time
            
            if move.clock_time:
                prev_time_by_color[move.color] = move.clock_time

class GameFilter:
    """Filter games based on various criteria"""
    
    @staticmethod
    def filter_by_player(games: List[ParsedGame], player_name: str) -> List[ParsedGame]:
        """Filter games where player_name participated"""
        return [game for game in games if game.player_color is not None]
    
    @staticmethod
    def filter_by_time_control(games: List[ParsedGame], time_control_pattern: str) -> List[ParsedGame]:
        """Filter games by time control pattern"""
        return [game for game in games 
                if game.metadata.time_control and 
                time_control_pattern.lower() in game.metadata.time_control.lower()]
    
    @staticmethod
    def filter_by_rating_range(games: List[ParsedGame], 
                              min_rating: Optional[int] = None, 
                              max_rating: Optional[int] = None) -> List[ParsedGame]:
        """Filter games by opponent rating range"""
        filtered = []
        for game in games:
            if game.player_color == "white":
                opp_rating = game.metadata.black_elo
            else:
                opp_rating = game.metadata.white_elo
                
            if opp_rating is None:
                continue
                
            if min_rating and opp_rating < min_rating:
                continue
            if max_rating and opp_rating > max_rating:
                continue
                
            filtered.append(game)
        
        return filtered
    
    @staticmethod
    def filter_by_result(games: List[ParsedGame], result: str) -> List[ParsedGame]:
        """Filter games by result (from player's perspective)"""
        filtered = []
        for game in games:
            if result == "win":
                if (game.player_color == "white" and game.metadata.result == "1-0") or \
                   (game.player_color == "black" and game.metadata.result == "0-1"):
                    filtered.append(game)
            elif result == "loss":
                if (game.player_color == "white" and game.metadata.result == "0-1") or \
                   (game.player_color == "black" and game.metadata.result == "1-0"):
                    filtered.append(game)
            elif result == "draw":
                if game.metadata.result == "1/2-1/2":
                    filtered.append(game)
        
        return filtered

if __name__ == "__main__":
    # Test the parser
    parser = PGNParser("v7p3r")
    games = parser.parse_file(Path("../../data/lichess_v7p3r_2025-10-02.pgn"))
    print(f"Parsed {len(games)} games")
    
    if games:
        game = games[0]
        print(f"Sample game: {game.metadata.white} vs {game.metadata.black}")
        print(f"Player color: {game.player_color}")
        print(f"Moves: {len(game.moves)}")
        print(f"First few moves: {[f'{m.move_number}.{m.san}' for m in game.moves[:6]]}")