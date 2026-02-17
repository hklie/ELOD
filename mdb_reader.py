#!/usr/bin/env python3
"""
MDB Reader for extracting tournament rankings from Microsoft Access databases.

This module reads .mdb files (typically from Scrabble tournament software)
and extracts player rankings that can be consumed by the ELO ranking system.

Requires: mdbtools (apt-get install mdbtools)
"""

import subprocess
import csv
from io import StringIO
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


class MdbReaderError(Exception):
    """Custom exception for MDB reader errors."""
    pass


@dataclass
class PlayerResult:
    """Represents a player's tournament result."""
    player_id: int
    name: str
    acronym: str
    final_score: int
    rank: int = 0


class MdbReader:
    """
    Reads Microsoft Access .mdb files and extracts tournament data.

    This reader is designed for tournament databases that contain:
    - Jugadores (Players) table: player ID, name, acronym
    - Relaciones table: scores per player per round

    Attributes:
        mdb_path: Path to the .mdb file
    """

    def __init__(self, mdb_path: str):
        """
        Initialize the MDB reader.

        Args:
            mdb_path: Path to the .mdb file
        """
        self.mdb_path = Path(mdb_path)
        if not self.mdb_path.exists():
            raise MdbReaderError(f"MDB file not found: {mdb_path}")

    def _run_mdb_command(self, command: str, *args) -> str:
        """
        Run an mdbtools command and return output.

        Args:
            command: The mdb command (e.g., 'mdb-tables', 'mdb-export')
            *args: Additional arguments

        Returns:
            Command output as string

        Raises:
            MdbReaderError: If command fails
        """
        cmd = [command, str(self.mdb_path)] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )
            # Explicitly decode as UTF-8 to handle Spanish characters properly
            return result.stdout.decode('utf-8')
        except subprocess.CalledProcessError as e:
            raise MdbReaderError(f"Command failed: {' '.join(cmd)}\n{e.stderr.decode('utf-8', errors='replace')}")
        except FileNotFoundError:
            raise MdbReaderError(
                f"mdbtools not found. Install with: sudo apt-get install mdbtools"
            )

    def list_tables(self) -> List[str]:
        """
        List all tables in the database.

        Returns:
            List of table names
        """
        output = self._run_mdb_command('mdb-tables', '-1')
        return [t.strip() for t in output.strip().split('\n') if t.strip()]

    def export_table(self, table_name: str) -> List[Dict]:
        """
        Export a table as a list of dictionaries.

        Args:
            table_name: Name of the table to export

        Returns:
            List of row dictionaries
        """
        output = self._run_mdb_command('mdb-export', table_name)
        reader = csv.DictReader(StringIO(output))
        return list(reader)

    def get_players(self) -> Dict[int, Tuple[str, str]]:
        """
        Get all players from the Jugadores table.

        Returns:
            Dictionary mapping player ID to (name, acronym)
        """
        rows = self.export_table('Jugadores')
        players = {}
        for row in rows:
            player_id = int(row['Indice'])
            name = row['Nombre'].strip()
            acronym = row.get('Acronim', '').strip()
            # Skip MASTER player (ID 1 is typically the system)
            if name.upper() != 'MASTER':
                players[player_id] = (name, acronym)
        return players

    def get_scores_by_round(self) -> Dict[int, Dict[int, Tuple[int, int]]]:
        """
        Get scores for all players organized by round.

        Returns:
            Dictionary mapping player_id -> {round -> (score, accumulated)}
        """
        rows = self.export_table('Relaciones')
        scores: Dict[int, Dict[int, Tuple[int, int]]] = {}

        for row in rows:
            player_id = int(row['Jugador'])
            round_num = int(row['Ronda'])
            score = int(row['Puntuacion'])
            accumulated = int(row['PuntuacionAcumulada'])

            if player_id not in scores:
                scores[player_id] = {}
            scores[player_id][round_num] = (score, accumulated)

        return scores

    def get_max_round(self) -> int:
        """Get the maximum round number in the tournament."""
        rows = self.export_table('Relaciones')
        return max(int(row['Ronda']) for row in rows)

    def detect_stopped_players(self, cutoff_round: int = 15) -> Tuple[List[int], List[int]]:
        """
        Detect players who stopped playing after a certain round.

        Players are considered "stopped" if all their scores after cutoff_round are 0.

        Args:
            cutoff_round: The round after which to check for zeros (default: 15)

        Returns:
            Tuple of (full_players, stopped_players) - lists of player IDs
        """
        scores = self.get_scores_by_round()
        max_round = self.get_max_round()

        full_players = []
        stopped_players = []

        for player_id, rounds in scores.items():
            # Check if all scores after cutoff_round are 0
            scores_after_cutoff = [
                rounds.get(r, (0, 0))[0]  # Get the score (not accumulated)
                for r in range(cutoff_round + 1, max_round + 1)
            ]

            if scores_after_cutoff and all(s == 0 for s in scores_after_cutoff):
                stopped_players.append(player_id)
            else:
                full_players.append(player_id)

        return full_players, stopped_players

    def get_final_scores(self) -> Dict[int, int]:
        """
        Get final accumulated scores for all players.

        Extracts the last round's accumulated score for each player.

        Returns:
            Dictionary mapping player ID to final score
        """
        rows = self.export_table('Relaciones')

        # Find max round and get final scores
        player_scores: Dict[int, Tuple[int, int]] = {}  # player_id -> (round, score)

        for row in rows:
            player_id = int(row['Jugador'])
            round_num = int(row['Ronda'])
            accumulated = int(row['PuntuacionAcumulada'])

            # Keep track of highest round for each player
            if player_id not in player_scores or round_num > player_scores[player_id][0]:
                player_scores[player_id] = (round_num, accumulated)

        return {pid: score for pid, (_, score) in player_scores.items()}

    def get_scores_at_round(self, round_num: int) -> Dict[int, int]:
        """
        Get accumulated scores for all players at a specific round.

        Args:
            round_num: The round number to get scores for

        Returns:
            Dictionary mapping player ID to accumulated score at that round
        """
        scores = self.get_scores_by_round()
        return {
            player_id: rounds.get(round_num, (0, 0))[1]  # Get accumulated score
            for player_id, rounds in scores.items()
        }

    def get_rankings(self) -> List[PlayerResult]:
        """
        Get final tournament rankings.

        Returns:
            List of PlayerResult objects sorted by score (highest first)
        """
        players = self.get_players()
        scores = self.get_final_scores()

        results = []
        for player_id, (name, acronym) in players.items():
            score = scores.get(player_id, 0)
            results.append(PlayerResult(
                player_id=player_id,
                name=name,
                acronym=acronym,
                final_score=score
            ))

        # Sort by score descending
        results.sort(key=lambda x: x.final_score, reverse=True)

        # Assign ranks
        for i, result in enumerate(results, 1):
            result.rank = i

        return results

    def get_split_rankings(self, cutoff_round: int = 15) -> Tuple[List[PlayerResult], List[PlayerResult]]:
        """
        Get separate rankings for full players and stopped players.

        Full players are ranked by their final score.
        Stopped players are ranked by their score at the cutoff round.

        Args:
            cutoff_round: The round where stopped players' scores are taken (default: 15)

        Returns:
            Tuple of (full_rankings, stopped_rankings) - each is a list of PlayerResult
        """
        players = self.get_players()
        full_player_ids, stopped_player_ids = self.detect_stopped_players(cutoff_round)

        final_scores = self.get_final_scores()
        cutoff_scores = self.get_scores_at_round(cutoff_round)

        # Build full player rankings
        full_results = []
        for player_id in full_player_ids:
            if player_id not in players:
                continue
            name, acronym = players[player_id]
            score = final_scores.get(player_id, 0)
            full_results.append(PlayerResult(
                player_id=player_id,
                name=name,
                acronym=acronym,
                final_score=score
            ))

        full_results.sort(key=lambda x: x.final_score, reverse=True)
        for i, result in enumerate(full_results, 1):
            result.rank = i

        # Build stopped player rankings (using cutoff round scores)
        stopped_results = []
        for player_id in stopped_player_ids:
            if player_id not in players:
                continue
            name, acronym = players[player_id]
            score = cutoff_scores.get(player_id, 0)
            stopped_results.append(PlayerResult(
                player_id=player_id,
                name=name,
                acronym=acronym,
                final_score=score
            ))

        stopped_results.sort(key=lambda x: x.final_score, reverse=True)
        for i, result in enumerate(stopped_results, 1):
            result.rank = i

        return full_results, stopped_results

    def export_for_elod(self, output_path: Optional[str] = None,
                        use_acronym: bool = False,
                        format_type: str = 'names') -> str:
        """
        Export rankings in a format suitable for the ELO system.

        Args:
            output_path: Path to write the output file (optional)
            use_acronym: If True, use acronyms instead of full names
            format_type: 'names' for one name per line,
                        'detailed' for full details

        Returns:
            The exported content as a string
        """
        rankings = self.get_rankings()

        lines = []
        for result in rankings:
            name = result.acronym if use_acronym else result.name
            # Clean name: remove spaces for concatenated format compatibility
            clean_name = name.replace(' ', '')

            if format_type == 'names':
                lines.append(clean_name)
            elif format_type == 'detailed':
                lines.append(f"{result.rank}\t{clean_name}\t{result.final_score}")

        content = '\n'.join(lines) + '\n'

        if output_path:
            Path(output_path).write_text(content, encoding='utf-8')

        return content

    def export_clasificacion_resumida(self, output_path: Optional[str] = None) -> str:
        """
        Export a summary classification (Clasificacion_Resumida format).

        Args:
            output_path: Path to write the output file

        Returns:
            The classification content
        """
        rankings = self.get_rankings()

        lines = []
        lines.append("=" * 60)
        lines.append("CLASIFICACIÓN RESUMIDA")
        lines.append("=" * 60)
        lines.append(f"{'Pos':>4}  {'Jugador':<30}  {'Puntos':>8}")
        lines.append("-" * 60)

        for result in rankings:
            lines.append(f"{result.rank:>4}  {result.name:<30}  {result.final_score:>8}")

        lines.append("-" * 60)
        lines.append(f"Total jugadores: {len(rankings)}")
        lines.append("")

        content = '\n'.join(lines)

        if output_path:
            Path(output_path).write_text(content, encoding='utf-8')

        return content


def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Extract tournament rankings from MDB files'
    )
    parser.add_argument(
        'mdb_file',
        help='Path to the .mdb file'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file path'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['names', 'detailed', 'clasificacion'],
        default='names',
        help='Output format (default: names)'
    )
    parser.add_argument(
        '--acronym', '-a',
        action='store_true',
        help='Use acronyms instead of full names'
    )
    parser.add_argument(
        '--list-tables',
        action='store_true',
        help='List all tables in the database'
    )

    args = parser.parse_args()

    reader = MdbReader(args.mdb_file)

    if args.list_tables:
        print("Tables in database:")
        for table in reader.list_tables():
            print(f"  - {table}")
        return

    if args.format == 'clasificacion':
        content = reader.export_clasificacion_resumida(args.output)
    else:
        content = reader.export_for_elod(
            output_path=args.output,
            use_acronym=args.acronym,
            format_type=args.format
        )

    if not args.output:
        print(content)
    else:
        print(f"Written to: {args.output}")


if __name__ == '__main__':
    main()
