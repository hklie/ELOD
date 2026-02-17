"""
ELO Math utilities for rating calculations.

This module provides mathematical functions for ELO rating calculations,
including the error function approximation and expected win probability.
"""

import math


class EloMath:
    """ELO rating calculation utilities."""

    # K-factor thresholds
    K_NEW_PLAYER = 25      # K-factor for players with < 50 games
    K_EXPERIENCED = 10     # K-factor for players with >= 50 games
    GAMES_THRESHOLD = 50   # Games threshold for K-factor change

    # Rating difference factor (standard ELO uses 400)
    RATING_FACTOR = 400

    @staticmethod
    def erf2(x: float) -> float:
        """
        Unnormalized error function approximation.

        This is a polynomial approximation of the error function
        used in probability calculations.

        Args:
            x: Input value

        Returns:
            Approximated error function value (unnormalized)
        """
        # Constants for the approximation
        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        # Save the sign of x
        sign = 1 if x >= 0 else -1
        x = abs(x)

        # Approximation formula
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

        return sign * y

    @staticmethod
    def erf(x: float) -> float:
        """
        Normalized error function.

        Wrapper around erf2 that normalizes by sqrt(2).

        Args:
            x: Input value

        Returns:
            Normalized error function value
        """
        return EloMath.erf2(x / math.sqrt(2))

    @staticmethod
    def expected_win(rating1: float, rating2: float) -> float:
        """
        Calculate the expected win probability for player 1.

        Uses the error function to compute the probability that
        player 1 beats player 2 based on their rating difference.

        Args:
            rating1: ELO rating of player 1
            rating2: ELO rating of player 2

        Returns:
            Probability (0-1) that player 1 wins
        """
        rating_diff = rating1 - rating2
        return (1 + EloMath.erf2(rating_diff / EloMath.RATING_FACTOR)) / 2

    @staticmethod
    def elo_gain(player_rating: float, opponent_rating: float,
                 actual_result: float, player_games: int) -> float:
        """
        Calculate ELO rating change for a single match.

        Args:
            player_rating: Current ELO rating of the player
            opponent_rating: Current ELO rating of the opponent
            actual_result: 1 for win, 0 for loss, 0.5 for draw
            player_games: Number of games the player has played (for K-factor)

        Returns:
            ELO rating change (positive or negative)
        """
        # Determine K-factor based on experience
        k_factor = (EloMath.K_NEW_PLAYER
                   if player_games < EloMath.GAMES_THRESHOLD
                   else EloMath.K_EXPERIENCED)

        # Calculate expected result
        expected = EloMath.expected_win(player_rating, opponent_rating)

        # Calculate and return ELO change
        return k_factor * (actual_result - expected)
