"""
Player model for ELO ranking system.

This module defines the Player class that holds player statistics
including ELO rating, games played, and tournament history.
"""

from dataclasses import dataclass, field
from typing import Optional
import copy


@dataclass
class Player:
    """
    Represents a player in the ELO ranking system.

    Attributes:
        elo: Current ELO rating (default: 1800)
        initial_elo: ELO rating at the start of calculations
        games: Total number of games played
        tourneys: Total number of tournaments participated
        last_tourney: Name of the last tournament played
    """

    elo: float = 1800.0
    initial_elo: float = 1800.0
    games: int = 0
    tourneys: int = 0
    last_tourney: str = "-"

    @property
    def delta_elo(self) -> float:
        """Calculate the change in ELO from initial to current."""
        return self.elo - self.initial_elo

    def __lt__(self, other: 'Player') -> bool:
        """Compare players by ELO for sorting (higher ELO first)."""
        return self.elo > other.elo  # Reversed for descending sort

    def __eq__(self, other: object) -> bool:
        """Check equality based on ELO rating."""
        if not isinstance(other, Player):
            return NotImplemented
        return self.elo == other.elo

    def copy(self) -> 'Player':
        """Create a deep copy of this player."""
        return Player(
            elo=self.elo,
            initial_elo=self.initial_elo,
            games=self.games,
            tourneys=self.tourneys,
            last_tourney=self.last_tourney
        )

    def __repr__(self) -> str:
        return (f"Player(elo={self.elo:.2f}, initial_elo={self.initial_elo:.2f}, "
                f"games={self.games}, tourneys={self.tourneys}, "
                f"last_tourney='{self.last_tourney}')")
