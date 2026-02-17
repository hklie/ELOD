"""
Tournament model for ELO ranking system.

This module defines the Tournament class that reads and parses
tournament result files containing sorted player rankings.
"""

from pathlib import Path
from typing import List, Optional


class TournamentError(Exception):
    """Custom exception for tournament-related errors."""
    pass


class Tournament:
    """
    Represents a tournament with ranked player results.

    The tournament file contains player names in order of their
    finishing position (1st place first, last place last).

    Attributes:
        name: Tournament filename/identifier
        players: List of player names in ranking order
        base_path: Base directory for tournament files
    """

    NAME_SIZE = 30  # Padding size for formatted output

    def __init__(self, filename: str, base_path: Optional[str] = None):
        """
        Initialize a tournament.

        Args:
            filename: Name of the tournament file
            base_path: Base directory containing tournament files
        """
        self.name = filename
        self.players: List[str] = []
        self.base_path = Path(base_path) if base_path else Path(".")

    def read_tournament(self) -> List[str]:
        """
        Read and parse the tournament file.

        The file should contain player names separated by whitespace,
        in order of their finishing position.

        Returns:
            List of player names in ranking order

        Raises:
            TournamentError: If file cannot be read or parsed
        """
        file_path = self.base_path / self.name

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Split by whitespace to get player names
                self.players = content.split()
        except FileNotFoundError:
            raise TournamentError(f"Tournament file not found: {file_path}")
        except IOError as e:
            raise TournamentError(f"Error reading tournament file: {e}")

        return self.players

    @staticmethod
    def pad_name(name: str, size: int = 30) -> str:
        """
        Pad a name to a fixed width for formatted output.

        Args:
            name: Player name to pad
            size: Target width (default: 30)

        Returns:
            Padded name string
        """
        return name.ljust(size)

    @staticmethod
    def pad_number(num: int) -> str:
        """
        Pad a number to 2 digits.

        Args:
            num: Number to format

        Returns:
            Formatted number string

        Raises:
            TournamentError: If number has more than 2 digits
        """
        if num < 0 or num > 99:
            raise TournamentError(f"Number {num} cannot be padded to 2 digits")
        return f"{num:2d}"

    def __repr__(self) -> str:
        return f"Tournament(name='{self.name}', players={len(self.players)})"
