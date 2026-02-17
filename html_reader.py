#!/usr/bin/env python3
"""
HTML Reader for extracting tournament rankings from DupMaster classification pages.

This module reads HTML files exported by DupMaster (e.g., Clasificacion.html)
and extracts player rankings that can be consumed by the ELO ranking system.

No external dependencies required — uses Python's built-in html.parser.
"""

from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


class HtmlReaderError(Exception):
    """Custom exception for HTML reader errors."""
    pass


@dataclass
class HtmlPlayerResult:
    """Represents a player's tournament result from an HTML classification."""
    name: str
    total_score: int
    rank: int = 0


class _TableParser(HTMLParser):
    """Internal HTML parser that extracts the first <table> data."""

    def __init__(self):
        super().__init__()
        self.in_first_table = False
        self.table_done = False
        self.in_row = False
        self.in_header_cell = False
        self.in_data_cell = False
        self.current_row: List[str] = []
        self.header_row: List[str] = []
        self.data_rows: List[List[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and not self.table_done:
            self.in_first_table = True
        elif self.in_first_table:
            if tag == 'tr':
                self.in_row = True
                self.current_row = []
            elif tag == 'th' and self.in_row:
                self.in_header_cell = True
            elif tag == 'td' and self.in_row:
                self.in_data_cell = True

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_first_table:
            self.in_first_table = False
            self.table_done = True
        elif self.in_first_table:
            if tag == 'tr' and self.in_row:
                self.in_row = False
                if self.current_row:
                    if self.header_row:
                        self.data_rows.append(self.current_row)
                    else:
                        self.header_row = self.current_row
            elif tag == 'th':
                self.in_header_cell = False
            elif tag == 'td':
                self.in_data_cell = False

    def handle_data(self, data):
        if self.in_header_cell or self.in_data_cell:
            # Append to last cell or start new one
            if self.current_row and (self.in_header_cell or self.in_data_cell):
                # If we already added a cell for this tag, append to it
                pass
            self.current_row.append(data.strip())

    def handle_entityref(self, name):
        if self.in_data_cell:
            if name == 'nbsp':
                self.current_row.append('')

    def handle_charref(self, name):
        if self.in_data_cell:
            if name == '160' or name == 'x00a0':
                self.current_row.append('')


class _RobustTableParser(HTMLParser):
    """
    A more robust HTML parser that tracks cell boundaries using
    start/end tags rather than relying on handle_data calls.
    """

    def __init__(self):
        super().__init__()
        self.in_first_table = False
        self.table_done = False
        self.in_row = False
        self.in_cell = False  # th or td
        self.cell_is_header = False
        self.cell_content = ''
        self.current_row: List[str] = []
        self.current_row_is_header = False
        self.header_row: List[str] = []
        self.data_rows: List[List[str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table' and not self.table_done:
            self.in_first_table = True
        elif self.in_first_table:
            if tag == 'tr':
                self.in_row = True
                self.current_row = []
                self.current_row_is_header = False
            elif tag in ('th', 'td') and self.in_row:
                self.in_cell = True
                self.cell_is_header = (tag == 'th')
                self.cell_content = ''
                if tag == 'th':
                    self.current_row_is_header = True

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_first_table:
            self.in_first_table = False
            self.table_done = True
        elif self.in_first_table:
            if tag in ('th', 'td') and self.in_cell:
                self.current_row.append(self.cell_content.strip())
                self.in_cell = False
            elif tag == 'tr' and self.in_row:
                self.in_row = False
                if self.current_row:
                    if self.current_row_is_header and not self.header_row:
                        self.header_row = self.current_row
                    else:
                        self.data_rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_cell:
            self.cell_content += data

    def handle_entityref(self, name):
        if self.in_cell:
            if name == 'nbsp':
                # Mark as empty — use a sentinel that we strip later
                self.cell_content += '\x00'
            else:
                self.cell_content += f'&{name};'

    def handle_charref(self, name):
        if self.in_cell:
            if name == '160' or name.lower() == 'x00a0':
                self.cell_content += '\x00'
            else:
                self.cell_content += chr(int(name, 16) if name.startswith('x') else int(name))


class HtmlReader:
    """
    Reads DupMaster HTML classification pages and extracts tournament data.

    The expected HTML format is a <table> with:
    - Header row: JUGADOR, round numbers (1..N), TOTAL, %, DIFER
    - First data row: MASTER (reference scores) — skipped
    - Subsequent rows: players sorted by TOTAL descending
    - Empty round cells (&nbsp;) indicate rounds not played

    Attributes:
        html_path: Path to the HTML file
    """

    # Columns after the round columns
    TRAILING_COLUMNS = {'TOTAL', '%', 'DIFER'}

    def __init__(self, html_path: str):
        self.html_path = Path(html_path)
        if not self.html_path.exists():
            raise HtmlReaderError(f"HTML file not found: {html_path}")

        self._header: List[str] = []
        self._rows: List[List[str]] = []
        self._num_rounds: int = 0
        self._parse()

    def _parse(self) -> None:
        """Parse the HTML file and extract table data."""
        # Try multiple encodings common in DupMaster exports
        content = None
        for encoding in ('utf-8', 'latin-1', 'cp1252'):
            try:
                content = self.html_path.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            raise HtmlReaderError(f"Could not decode HTML file: {self.html_path}")

        parser = _RobustTableParser()
        parser.feed(content)

        if not parser.header_row:
            raise HtmlReaderError(f"No table header found in: {self.html_path}")
        if not parser.data_rows:
            raise HtmlReaderError(f"No data rows found in: {self.html_path}")

        self._header = parser.header_row

        # Determine number of rounds from header
        # Header: JUGADOR, 1, 2, ..., N, TOTAL, %, DIFER
        round_cols = [h for h in self._header[1:] if h not in self.TRAILING_COLUMNS]
        self._num_rounds = len(round_cols)

        # Skip MASTER row (first data row)
        all_rows = parser.data_rows
        if all_rows and all_rows[0] and all_rows[0][0].upper() == 'MASTER':
            self._rows = all_rows[1:]
        else:
            self._rows = all_rows

    def _is_cell_empty(self, cell: str) -> bool:
        """Check if a cell represents an unplayed round (&nbsp; or empty)."""
        return cell == '' or cell == '\x00' or cell.strip('\x00').strip() == ''

    def _get_round_cells(self, row: List[str]) -> List[str]:
        """Extract just the round score cells from a row (columns 1..N)."""
        # Column 0 is player name, columns 1..num_rounds are round scores
        return row[1:1 + self._num_rounds]

    def _detect_stopped(self, row: List[str]) -> bool:
        """
        Detect if a player stopped playing before the tournament ended.

        A player is "stopped" if their last N round cells are all empty (&nbsp;),
        meaning they have trailing empty rounds from some point onward.
        Players with scattered empty cells who played later rounds are NOT stopped.
        """
        round_cells = self._get_round_cells(row)
        if not round_cells:
            return False

        # Find the last non-empty round
        last_played = -1
        for i in range(len(round_cells) - 1, -1, -1):
            if not self._is_cell_empty(round_cells[i]):
                last_played = i
                break

        if last_played == -1:
            # All rounds empty — consider stopped
            return True

        # Player is "stopped" if they didn't play the last round
        # (i.e., they have trailing empty rounds)
        return last_played < len(round_cells) - 1

    def _get_total_score(self, row: List[str]) -> int:
        """Extract the TOTAL score from a row."""
        # TOTAL is the column right after the round columns
        total_idx = 1 + self._num_rounds
        if total_idx < len(row):
            try:
                return int(row[total_idx].strip('\x00').strip())
            except (ValueError, IndexError):
                return 0
        return 0

    def get_rankings(self) -> List[HtmlPlayerResult]:
        """
        Get tournament rankings from the HTML classification.

        Returns:
            List of HtmlPlayerResult sorted by score (row order, already ranked)
        """
        results = []
        for rank, row in enumerate(self._rows, 1):
            if not row:
                continue
            name = row[0].strip('\x00').strip()
            if not name:
                continue
            total = self._get_total_score(row)
            results.append(HtmlPlayerResult(name=name, total_score=total, rank=rank))
        return results

    def get_split_rankings(self, cutoff_round: int = 15) -> Tuple[List[HtmlPlayerResult], List[HtmlPlayerResult]]:
        """
        Get separate rankings for full players and stopped players.

        A player is considered "stopped" if they have trailing empty rounds
        and their last played round is at or before the cutoff_round.

        Args:
            cutoff_round: Round threshold — players who stopped at or before
                         this round are classified as stopped (default: 15)

        Returns:
            Tuple of (full_rankings, stopped_rankings)
        """
        full_results = []
        stopped_results = []

        for row in self._rows:
            if not row:
                continue
            name = row[0].strip('\x00').strip()
            if not name:
                continue
            total = self._get_total_score(row)
            result = HtmlPlayerResult(name=name, total_score=total)

            if self._detect_stopped(row):
                # Check if they stopped at or before the cutoff round
                round_cells = self._get_round_cells(row)
                last_played = -1
                for i in range(len(round_cells) - 1, -1, -1):
                    if not self._is_cell_empty(round_cells[i]):
                        last_played = i
                        break

                # last_played is 0-indexed, cutoff_round is 1-indexed
                if last_played < cutoff_round:
                    stopped_results.append(result)
                else:
                    full_results.append(result)
            else:
                full_results.append(result)

        # Assign ranks within each group
        for i, r in enumerate(full_results, 1):
            r.rank = i
        for i, r in enumerate(stopped_results, 1):
            r.rank = i

        return full_results, stopped_results
