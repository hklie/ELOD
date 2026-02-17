#!/usr/bin/env python3
"""
Test script to validate Python ELO implementation against Java output.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from elo_math import EloMath
from player import Player
from tournament import Tournament
from elod import Elod


def test_elo_math():
    """Test ELO math calculations."""
    print("=" * 60)
    print("Testing EloMath")
    print("=" * 60)

    # Test expected win probability
    # Equal ratings should give 0.5
    prob = EloMath.expected_win(1800, 1800)
    print(f"Expected win (1800 vs 1800): {prob:.4f} (expected ~0.5)")
    assert abs(prob - 0.5) < 0.01, "Expected 0.5 for equal ratings"

    # Higher rated player should have > 0.5 probability
    prob = EloMath.expected_win(1900, 1800)
    print(f"Expected win (1900 vs 1800): {prob:.4f} (expected > 0.5)")
    assert prob > 0.5, "Higher rated should have > 0.5 probability"

    # Test ELO gain for a win
    gain = EloMath.elo_gain(1800, 1800, 1, 50)
    print(f"ELO gain (1800 beats 1800): {gain:.4f}")
    assert gain > 0, "Winner should gain ELO"

    # Test ELO gain for a loss
    loss = EloMath.elo_gain(1800, 1800, 0, 50)
    print(f"ELO loss (1800 loses to 1800): {loss:.4f}")
    assert loss < 0, "Loser should lose ELO"

    # Gain and loss should be symmetric
    print(f"Symmetric check: {gain:.4f} + {loss:.4f} = {gain + loss:.4f}")
    assert abs(gain + loss) < 0.01, "Gain and loss should be symmetric"

    print("EloMath tests PASSED\n")


def test_player():
    """Test Player class."""
    print("=" * 60)
    print("Testing Player")
    print("=" * 60)

    p1 = Player(elo=1850, games=10, tourneys=2, last_tourney="test1")
    p2 = Player(elo=1750, games=5, tourneys=1, last_tourney="test2")

    print(f"Player 1: {p1}")
    print(f"Player 2: {p2}")

    # Test comparison (higher ELO should be "less than" for descending sort)
    assert p1 < p2, "Higher ELO player should sort first"
    print("Sorting comparison: PASSED")

    # Test copy
    p3 = p1.copy()
    p3.elo = 1900
    assert p1.elo == 1850, "Original should be unchanged after copy modification"
    print("Deep copy: PASSED")

    print("Player tests PASSED\n")


def test_tournament():
    """Test Tournament class."""
    print("=" * 60)
    print("Testing Tournament")
    print("=" * 60)

    base_path = Path(__file__).parent / "resources" / "FILE"
    tournament = Tournament("game_test.txt", str(base_path))
    players = tournament.read_tournament()

    print(f"Tournament: {tournament}")
    print(f"Players: {players}")

    assert len(players) == 5, f"Expected 5 players, got {len(players)}"
    assert players[0] == "Alice", "First player should be Alice"
    assert players[-1] == "Eve", "Last player should be Eve"

    print("Tournament tests PASSED\n")


def test_full_calculation():
    """Test full ELO calculation and compare with Java output."""
    print("=" * 60)
    print("Testing Full ELO Calculation")
    print("=" * 60)

    base_path = Path(__file__).parent / "resources" / "FILE"
    output_path = Path(__file__).parent / "resources"

    elod = Elod(base_path=str(base_path))
    results = elod.run(
        players_file="inicio.elod",
        tournament_files=["game_test.txt"],
        output_path=str(output_path),
        verbose=True
    )

    print("\nResults:")
    print("-" * 50)

    # Expected results from Java execution
    expected = {
        "Alice": 1820,
        "Bob": 1810,
        "Charlie": 1800,
        "Diana": 1790,
        "Eve": 1780,
    }

    all_match = True
    for name, player in elod.sort_players().items():
        expected_elo = expected.get(name, 0)
        actual_elo = round(player.elo)
        match = "OK" if actual_elo == expected_elo else "MISMATCH"
        if actual_elo != expected_elo:
            all_match = False
        print(f"{name:10s}  ELO: {actual_elo:4d} (expected: {expected_elo:4d})  "
              f"Games: {player.games:2d}  Tourneys: {player.tourneys}  [{match}]")

    print("-" * 50)

    if all_match:
        print("Full calculation test PASSED - matches Java output!")
    else:
        print("Full calculation test FAILED - does not match Java output")
        sys.exit(1)

    # Check output files
    post_file = output_path / "game_test.txt.post"
    final_file = output_path / "final.txt"

    print(f"\nGenerated files:")
    print(f"  - {post_file}: {'EXISTS' if post_file.exists() else 'MISSING'}")
    print(f"  - {final_file}: {'EXISTS' if final_file.exists() else 'MISSING'}")

    if final_file.exists():
        print(f"\nContents of final.txt:")
        print(final_file.read_text())


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ELO Ranking System - Python Validation Tests")
    print("=" * 60 + "\n")

    test_elo_math()
    test_player()
    test_tournament()
    test_full_calculation()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
