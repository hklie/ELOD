"""
ELO Ranking System for Tournaments

This package provides ELO rating calculations from sorted tournament results.
Includes utilities for reading Microsoft Access (.mdb) tournament databases.
"""

from .player import Player
from .tournament import Tournament
from .elo_math import EloMath
from .elod import Elod
from .mdb_reader import MdbReader, PlayerResult
from .html_reader import HtmlReader, HtmlPlayerResult

__all__ = ['Player', 'Tournament', 'EloMath', 'Elod', 'MdbReader', 'PlayerResult', 'HtmlReader', 'HtmlPlayerResult']
__version__ = '1.0.0'
