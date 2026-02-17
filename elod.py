"""
Main ELO ranking orchestrator.

This module provides the Elod class that coordinates the entire
ELO rating calculation process from tournament results.

Supports both .txt tournament files and .mdb Microsoft Access databases.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Set
from collections import OrderedDict, defaultdict
import copy
import unicodedata

# Default starting ELO for new players
DEFAULT_ELO = 2075.0


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison by removing accents and converting to lowercase.

    Args:
        name: The player name to normalize

    Returns:
        Normalized name (lowercase, no accents)
    """
    # Decompose unicode characters (é -> e + combining accent)
    nfkd = unicodedata.normalize('NFKD', name)
    # Remove combining characters (accents)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.lower()


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein (edit) distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Number of edits (insertions, deletions, substitutions) to transform s1 to s2
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_similar_names(names: List[str]) -> Tuple[Dict[str, List[str]], List[Tuple[str, str, int]]]:
    """
    Find groups of names that might be the same person with different spellings.

    Detects two types of similarities:
    1. Exact normalized matches (accent variations): "AiranPérez" vs "AiranPerez"
    2. Similar names by edit distance (nicknames): "XaviPiqué" vs "XavierPiqué"

    Args:
        names: List of player names

    Returns:
        Tuple of:
        - Dictionary mapping normalized name to list of original name variants
          (only includes groups with more than one variant)
        - List of (name1, name2, distance) tuples for similar but not exact matches
    """
    # Group by exact normalized match (accent variations)
    exact_groups: Dict[str, List[str]] = defaultdict(list)
    for name in names:
        normalized = normalize_name(name)
        exact_groups[normalized].append(name)

    exact_duplicates = {k: v for k, v in exact_groups.items() if len(v) > 1}

    # Find similar names by edit distance (for nickname detection)
    # Only compare names that weren't already matched exactly
    similar_pairs: List[Tuple[str, str, int]] = []
    normalized_names = [(name, normalize_name(name)) for name in names]

    # Get names that are already in exact duplicate groups
    exact_matched = set()
    for variants in exact_duplicates.values():
        exact_matched.update(variants)

    for i, (name1, norm1) in enumerate(normalized_names):
        for name2, norm2 in normalized_names[i + 1:]:
            # Skip if already matched exactly
            if name1 in exact_matched and name2 in exact_matched:
                if normalize_name(name1) == normalize_name(name2):
                    continue

            # Calculate similarity
            distance = levenshtein_distance(norm1, norm2)
            max_len = max(len(norm1), len(norm2))

            # Consider similar if edit distance is small relative to name length
            # Threshold: up to 3 edits for names >= 8 chars, or ~25% of length
            if max_len >= 6 and distance <= min(3, max_len * 0.3):
                # Additional check: names should share a common substring
                # (to avoid matching completely different short names)
                if len(set(norm1) & set(norm2)) >= min(len(norm1), len(norm2)) * 0.6:
                    similar_pairs.append((name1, name2, distance))

    return exact_duplicates, similar_pairs


def parse_aliases(alias_path: str) -> Dict[str, str]:
    """
    Parse a player name aliases file.

    Alias file format:
        - Lines starting with # are comments
        - Format: canonical_name = alias1, alias2, ...
        - Use semicolons (;) instead of commas when aliases contain commas
        - The canonical name (left side) will be used in results

    Example:
        # Player aliases
        AiranPérez = AiranPerez
        SolangeDíaz = SolangeDiaz, Solange
        # For aliases with commas, use semicolons:
        JoséGonzález = GONZALEZ,José; GONZALEZ,J

    Args:
        alias_path: Path to the alias file

    Returns:
        Dictionary mapping alias names to canonical names
    """
    aliases: Dict[str, str] = {}

    with open(alias_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            if '=' not in line:
                continue

            # Parse: canonical = alias1, alias2, ...
            parts = line.split('=', 1)
            canonical = parts[0].strip()
            alias_str = parts[1].strip()

            # Use semicolon as delimiter if present, otherwise comma
            delimiter = ';' if ';' in alias_str else ','
            alias_list = [a.strip() for a in alias_str.split(delimiter)]

            # Map each alias to the canonical name
            for alias in alias_list:
                if alias:
                    aliases[alias] = canonical

    return aliases


def load_deceased_players(file_path: str) -> Set[str]:
    """
    Load list of deceased players to exclude from rankings.

    Args:
        file_path: Path to file with deceased player names (one per line)

    Returns:
        Set of canonical player names to exclude
    """
    deceased: Set[str] = set()
    path = Path(file_path)
    if not path.exists():
        return deceased

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                deceased.add(line)

    return deceased


def apply_aliases(name: str, aliases: Dict[str, str]) -> str:
    """
    Apply name aliases to get the canonical name.

    Args:
        name: The player name (may be an alias)
        aliases: Dictionary mapping aliases to canonical names

    Returns:
        The canonical name if an alias exists, otherwise the original name
    """
    return aliases.get(name, name)


try:
    from .player import Player
    from .tournament import Tournament, TournamentError
    from .elo_math import EloMath
    from .mdb_reader import MdbReader, MdbReaderError
    from .html_reader import HtmlReader, HtmlReaderError
    from .image_reader import ImageReader, ImageReaderError
except ImportError:
    from player import Player
    from tournament import Tournament, TournamentError
    from elo_math import EloMath
    from mdb_reader import MdbReader, MdbReaderError
    from html_reader import HtmlReader, HtmlReaderError
    try:
        from image_reader import ImageReader, ImageReaderError
    except ImportError:
        ImageReader = None
        ImageReaderError = Exception


class TournamentData:
    """
    Unified tournament data container.

    Abstracts the source (txt or mdb) and provides a consistent interface.
    Supports split rankings for tournaments with players who stopped early.
    """

    def __init__(self, name: str, players: List[str], display_name: Optional[str] = None,
                 stopped_players: Optional[List[str]] = None):
        """
        Initialize tournament data.

        Args:
            name: Tournament identifier/filename
            players: List of player names in ranking order (1st place first) - full tournament players
            display_name: Human-readable tournament name (e.g., "Europeo Atenas 2022")
            stopped_players: List of player names who stopped early, ranked by their score at cutoff round
        """
        self.name = name
        self.players = players
        self.display_name = display_name or name
        self.stopped_players = stopped_players or []

    @property
    def all_players(self) -> List[str]:
        """Get all players (both full and stopped)."""
        return self.players + self.stopped_players

    def __repr__(self) -> str:
        stopped_info = f", stopped={len(self.stopped_players)}" if self.stopped_players else ""
        return f"TournamentData(name='{self.name}', display_name='{self.display_name}', players={len(self.players)}{stopped_info})"


class Elod:
    """
    Main orchestrator for ELO ranking calculations.

    Processes tournament files (.txt or .mdb) and calculates ELO rating changes
    for all participating players.

    Attributes:
        players: Dictionary mapping player names to Player objects
        tournament_files: List of tournament file paths to process
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {'.txt', '.mdb', '.accdb', '.jpeg', '.jpg', '.png', '.html', '.htm'}

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the Elod system.

        Args:
            base_path: Base directory for data files (optional, can use full paths)
        """
        self.players: Dict[str, Player] = {}
        self.tournament_files: List[str] = []
        self.base_path = Path(base_path) if base_path else None
        self.deceased_players: Set[str] = set()

    def _resolve_path(self, filepath: str) -> Path:
        """
        Resolve a file path, using base_path if path is relative.

        Args:
            filepath: File path (absolute or relative)

        Returns:
            Resolved Path object
        """
        path = Path(filepath)
        if path.is_absolute():
            return path
        elif self.base_path:
            return self.base_path / filepath
        else:
            return path

    def read_players(self, filename: str) -> Dict[str, Player]:
        """
        Load initial player ratings from a file.

        File format (tab-separated):
        PlayerName  ELO  Games  Tourneys  LastTourney

        Args:
            filename: Path to the players file (absolute or relative to base_path)

        Returns:
            Dictionary of player names to Player objects
        """
        file_path = self._resolve_path(filename)

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) >= 5:
                    name = parts[0]
                    elo = float(parts[1])
                    games = int(parts[2])
                    tourneys = int(parts[3])
                    last_tourney = parts[4]

                    self.players[name] = Player(
                        elo=elo,
                        games=games,
                        tourneys=tourneys,
                        last_tourney=last_tourney
                    )

        return self.players

    def read_players_from_tournament(self, tournament_file: str,
                                      default_elo: float = DEFAULT_ELO,
                                      aliases: Optional[Dict[str, str]] = None) -> Dict[str, Player]:
        """
        Initialize players from a tournament file (no prior inicio.elod needed).

        Useful when you don't have an existing player database and want to
        initialize all players with the same starting ELO.

        Args:
            tournament_file: Path to tournament file (.txt or .mdb)
            default_elo: Starting ELO for all players
            aliases: Dictionary mapping alias names to canonical names

        Returns:
            Dictionary of player names to Player objects
        """
        aliases = aliases or {}
        tournament_data = self.load_tournament(tournament_file)

        # Process all players (both full and stopped)
        for player_name in tournament_data.all_players:
            # Apply alias to get canonical name
            canonical_name = apply_aliases(player_name, aliases)
            if canonical_name not in self.players:
                self.players[canonical_name] = Player(
                    elo=default_elo,
                    initial_elo=default_elo,
                    games=0,
                    tourneys=0,
                    last_tourney="-"
                )

        return self.players

    def load_tournament(self, filepath: str, display_name: Optional[str] = None) -> TournamentData:
        """
        Load tournament data from either .txt or .mdb file.

        Args:
            filepath: Path to tournament file (absolute or relative)
            display_name: Human-readable tournament name (optional)

        Returns:
            TournamentData object with player rankings

        Raises:
            ValueError: If file extension is not supported
            TournamentError: If .txt file cannot be read
            MdbReaderError: If .mdb file cannot be read
        """
        file_path = self._resolve_path(filepath)
        extension = file_path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {extension}. "
                f"Supported: {self.SUPPORTED_EXTENSIONS}"
            )

        if extension in {'.mdb', '.accdb'}:
            return self._load_from_mdb(file_path, display_name)
        elif extension in {'.html', '.htm'}:
            return self._load_from_html(file_path, display_name)
        elif extension in {'.jpeg', '.jpg', '.png'}:
            return self._load_from_image(file_path, display_name)
        else:
            return self._load_from_txt(file_path, display_name)

    def _load_from_txt(self, file_path: Path, display_name: Optional[str] = None) -> TournamentData:
        """
        Load tournament data from a .txt file.

        Args:
            file_path: Path to the .txt file
            display_name: Human-readable tournament name (optional)

        Returns:
            TournamentData object
        """
        tournament = Tournament(file_path.name, str(file_path.parent))
        tournament.read_tournament()

        return TournamentData(
            name=file_path.name,
            players=tournament.players,
            display_name=display_name
        )

    def _load_from_mdb(self, file_path: Path, display_name: Optional[str] = None) -> TournamentData:
        """
        Load tournament data from a .mdb file.

        Extracts player rankings from the Access database.
        Detects players who stopped at round 15 and ranks them separately.

        Args:
            file_path: Path to the .mdb file
            display_name: Human-readable tournament name (optional)

        Returns:
            TournamentData object with separate full and stopped player rankings
        """
        reader = MdbReader(str(file_path))

        # Get split rankings (full players vs those who stopped at R15)
        full_rankings, stopped_rankings = reader.get_split_rankings(cutoff_round=15)

        # Extract player names in ranking order (spaces removed for consistency)
        players = [r.name.replace(' ', '') for r in full_rankings]
        stopped_players = [r.name.replace(' ', '') for r in stopped_rankings]

        return TournamentData(
            name=file_path.name,
            players=players,
            display_name=display_name,
            stopped_players=stopped_players
        )

    def _load_from_html(self, file_path: Path, display_name: Optional[str] = None) -> TournamentData:
        """
        Load tournament data from an HTML classification page (DupMaster export).

        Extracts player rankings from the HTML table.
        Detects players who stopped early and ranks them separately.

        Args:
            file_path: Path to the HTML file
            display_name: Human-readable tournament name (optional)

        Returns:
            TournamentData object with separate full and stopped player rankings
        """
        reader = HtmlReader(str(file_path))

        # Get split rankings (full players vs those who stopped early)
        full_rankings, stopped_rankings = reader.get_split_rankings(cutoff_round=15)

        # Extract player names in ranking order (spaces removed for consistency)
        players = [r.name.replace(' ', '') for r in full_rankings]
        stopped_players = [r.name.replace(' ', '') for r in stopped_rankings]

        return TournamentData(
            name=file_path.name,
            players=players,
            display_name=display_name,
            stopped_players=stopped_players
        )

    def _load_from_image(self, file_path: Path, display_name: Optional[str] = None) -> TournamentData:
        """
        Load tournament data from an image file (JPEG, PNG).

        Uses OCR to extract player rankings from tournament result images.
        Falls back to looking for a corresponding .txt file if OCR is not available.

        Args:
            file_path: Path to the image file
            display_name: Human-readable tournament name (optional)

        Returns:
            TournamentData object
        """
        # First, try to find a corresponding .txt file (manual extraction)
        txt_path = file_path.with_suffix('.txt')
        if txt_path.exists():
            return self._load_from_txt(txt_path, display_name)

        # Try OCR if ImageReader is available
        if ImageReader is None:
            raise ValueError(
                f"Cannot process image {file_path.name}: "
                f"No .txt file found and image_reader not available.\n"
                f"Either create {txt_path.name} manually or install pytesseract."
            )

        try:
            reader = ImageReader(str(file_path))
            rankings = reader.get_rankings()
            players = [r.name.replace(' ', '') for r in rankings]

            return TournamentData(
                name=file_path.name,
                players=players,
                display_name=display_name
            )
        except ImageReaderError as e:
            raise ValueError(f"Failed to read image {file_path.name}: {e}")

    def sort_players(self) -> OrderedDict:
        """
        Sort players by ELO rating in descending order.

        Returns:
            OrderedDict of players sorted by ELO (highest first)
        """
        sorted_items = sorted(
            self.players.items(),
            key=lambda x: x[1].elo,
            reverse=True
        )
        return OrderedDict(sorted_items)

    def write_results(self, tournament_name: str, is_final: bool = False,
                      output_path: Optional[str] = None) -> str:
        """
        Write current rankings to a CSV file.

        Args:
            tournament_name: Name of the tournament (for intermediate files)
            is_final: If True, writes to elod_final.csv
            output_path: Custom output directory

        Returns:
            Path to the written file
        """
        if output_path:
            out_dir = Path(output_path)
        elif self.base_path:
            out_dir = self.base_path
        else:
            out_dir = Path(".")

        # Ensure output directory exists
        out_dir.mkdir(parents=True, exist_ok=True)

        if is_final:
            out_file = out_dir / "elod_final.csv"
        else:
            # Remove .mdb/.txt extension if present for cleaner output filename
            clean_name = tournament_name.replace('.mdb', '').replace('.txt', '')
            out_file = out_dir / f"{clean_name}.csv"

        # Filter out deceased players from final rankings
        sorted_players = {k: v for k, v in self.sort_players().items()
                          if k not in self.deceased_players}

        # Use utf-8-sig for CSV files to include BOM (Excel compatibility)
        with open(out_file, 'w', encoding='utf-8-sig') as f:
            # CSV format with headers
            f.write("Posición,Jugador,ELOD Inicial,Delta ELOD,ELOD Final,N. Oponentes,N. Partidas,Ultimo Torneo\n")
            for position, (name, player) in enumerate(sorted_players.items(), start=1):
                delta = player.delta_elo
                delta_str = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
                f.write(f"{position},{name},{player.initial_elo:.0f},{delta_str},{player.elo:.0f},"
                       f"{player.games},{player.tourneys},{player.last_tourney}\n")

        return str(out_file)

    def _process_player_group(self, player_list: List[str], tournament_data: TournamentData,
                               players_updated: Dict[str, Player]) -> None:
        """
        Process ELO changes for a group of players competing against each other.

        Args:
            player_list: List of player names in ranking order
            tournament_data: TournamentData object (for display_name)
            players_updated: Dictionary to store updated player stats
        """
        for current_idx, current_name in enumerate(player_list):
            if current_name not in self.players:
                print(f"Warning: Player '{current_name}' not found in database")
                continue

            current_player = self.players[current_name]
            updated_player = players_updated[current_name]

            # Update tournament count and last tournament
            updated_player.tourneys += 1
            updated_player.last_tourney = tournament_data.display_name

            # Compare against all opponents in the same group
            for opponent_idx, opponent_name in enumerate(player_list):
                if current_name == opponent_name:
                    continue

                if opponent_name not in self.players:
                    continue

                opponent = self.players[opponent_name]

                # Determine match result based on position
                # Lower index = better position = won against higher indices
                match_result = 1 if current_idx < opponent_idx else 0

                # Calculate ELO gain (using 50 as games threshold like Java version)
                elo_change = EloMath.elo_gain(
                    current_player.elo,
                    opponent.elo,
                    match_result,
                    50  # Hardcoded as in original Java
                )

                updated_player.elo += elo_change
                updated_player.games += 1

    def process_tournament(self, tournament_data: TournamentData,
                          players_updated: Dict[str, Player]) -> None:
        """
        Process a single tournament and update player ratings.

        For each player in the tournament, calculates ELO changes
        based on pairwise comparisons with players in the same category.
        Full players compete against full players only.
        Stopped players (R15) compete against stopped players only.

        Args:
            tournament_data: TournamentData object with player rankings
            players_updated: Dictionary to store updated player stats
        """
        # Process full players (competed all rounds)
        self._process_player_group(tournament_data.players, tournament_data, players_updated)

        # Process stopped players (stopped at R15) - they compete only among themselves
        if tournament_data.stopped_players:
            self._process_player_group(tournament_data.stopped_players, tournament_data, players_updated)

    def run(self, players_file: Optional[str],
            tournament_files: List[Union[str, Tuple[str, str]]],
            output_path: Optional[str] = None,
            verbose: bool = True,
            auto_init_players: bool = False,
            default_elo: float = DEFAULT_ELO,
            aliases: Optional[Dict[str, str]] = None) -> Dict[str, Player]:
        """
        Run the complete ELO calculation process.

        Args:
            players_file: Path to initial player ratings file (None if auto_init)
            tournament_files: List of tournament file paths (.txt or .mdb),
                              or tuples of (path, display_name)
            output_path: Custom output directory for results
            verbose: If True, print progress messages
            auto_init_players: If True, auto-initialize players from tournaments
            default_elo: Starting ELO when auto-initializing players
            aliases: Dictionary mapping alias names to canonical names

        Returns:
            Final player rankings dictionary
        """
        aliases = aliases or {}

        # Normalize tournament_files to list of (path, display_name) tuples
        normalized_tournaments: List[Tuple[str, str]] = []
        for item in tournament_files:
            if isinstance(item, tuple):
                normalized_tournaments.append(item)
            else:
                # Use filename (without extension) as display name
                normalized_tournaments.append((item, Path(item).stem))

        self.tournament_files = [t[0] for t in normalized_tournaments]

        # Load or initialize players
        if players_file:
            self.read_players(players_file)

        if auto_init_players:
            # Pre-scan all tournaments to collect player names
            for tournament_file, _ in normalized_tournaments:
                self.read_players_from_tournament(tournament_file, default_elo, aliases)

        # Create deep copy for tracking updates
        players_updated: Dict[str, Player] = {
            name: player.copy() for name, player in self.players.items()
        }

        # Process each tournament
        for tournament_file, display_name in normalized_tournaments:
            # Load tournament data (auto-detects .txt or .mdb)
            tournament_data = self.load_tournament(tournament_file, display_name)

            # Apply aliases to player names (both full and stopped players)
            tournament_data.players = [
                apply_aliases(name, aliases) for name in tournament_data.players
            ]
            tournament_data.stopped_players = [
                apply_aliases(name, aliases) for name in tournament_data.stopped_players
            ]

            if verbose:
                file_type = Path(tournament_file).suffix.upper()
                stopped_info = f" + {len(tournament_data.stopped_players)} R15" if tournament_data.stopped_players else ""
                print(f"Processing [{file_type}]: {tournament_data.display_name} "
                      f"({len(tournament_data.players)} players{stopped_info})...")

            # Auto-add any new players found in this tournament (both categories)
            for player_name in tournament_data.all_players:
                if player_name not in self.players:
                    self.players[player_name] = Player(
                        elo=default_elo, initial_elo=default_elo,
                        games=0, tourneys=0, last_tourney="-"
                    )
                    players_updated[player_name] = self.players[player_name].copy()

            # Before processing: set initial_elo to current ELO for participating players
            # This way, initial_elo reflects ELO at start of THIS tournament
            for player_name in tournament_data.all_players:
                if player_name in players_updated:
                    players_updated[player_name].initial_elo = players_updated[player_name].elo

            # Process tournament
            self.process_tournament(tournament_data, players_updated)

            # Sync updates back to main players dict
            for name in self.players:
                if name in players_updated:
                    self.players[name].elo = players_updated[name].elo
                    self.players[name].initial_elo = players_updated[name].initial_elo
                    self.players[name].games = players_updated[name].games
                    self.players[name].tourneys = players_updated[name].tourneys
                    self.players[name].last_tourney = players_updated[name].last_tourney

            # Write intermediate results
            if output_path:
                self.write_results(tournament_data.name, is_final=False,
                                  output_path=output_path)

        # Write final results
        if output_path:
            self.write_results("", is_final=True, output_path=output_path)

        return self.players


def parse_manifest(manifest_path: str, base_path: Optional[str] = None) -> List[Tuple[str, str]]:
    """
    Parse a tournament manifest file (torneos.manifiesto).

    Formato del manifiesto:
        - Lineas que comienzan con # son comentarios
        - Fechas (DD-MM-YYYY) agrupan torneos y definen el nombre del evento despues de #
        - Archivos de torneos se listan debajo de cada fecha
        - Los torneos heredan el nombre del evento de su fecha

    Ejemplo:
        # Temporada de Torneos 2022
        15-07-2022  # Europeo Atenas 2022
        EuropeoAtenas2022.mdb

        20-10-2022  # Mundial Buenos Aires 2022
        PartidaBaAs1.mdb
        PartidaBaAs2.mdb
        PartidaBaAs3.mdb

    Args:
        manifest_path: Ruta al archivo de manifiesto
        base_path: Ruta base opcional para archivos de torneos relativos

    Returns:
        Lista de tuplas (ruta_torneo, nombre_display) en orden cronologico
    """
    import re

    tournaments = []
    # Accept both DD-MM-YYYY (Spanish) and YYYY-MM-DD (ISO) formats
    # Allow 1 or 2 digits for day and month
    date_pattern = re.compile(r'^(\d{1,2}-\d{1,2}-\d{4}|\d{4}-\d{2}-\d{2})')
    current_display_name = None

    manifest_file = Path(manifest_path)
    manifest_dir = manifest_file.parent

    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith('#'):
                continue

            # Check for date line with display name
            date_match = date_pattern.match(line)
            if date_match:
                # Extract display name from comment after date
                if '#' in line:
                    current_display_name = line.split('#', 1)[1].strip()
                else:
                    current_display_name = None
                continue

            # This is a tournament file
            tournament_path = line.split('#')[0].strip()  # Remove inline comments
            if not tournament_path:
                continue

            # Resolve path: try base_path first, then manifest directory
            resolved_path = None
            if base_path:
                full_path = Path(base_path) / tournament_path
                if full_path.exists():
                    resolved_path = str(full_path)

            if not resolved_path:
                # Try relative to manifest file location
                full_path = manifest_dir / tournament_path
                if full_path.exists():
                    resolved_path = str(full_path)
                else:
                    # Use as-is (might be absolute or will fail later with clear error)
                    resolved_path = tournament_path

            # Use current display name or filename as fallback
            display_name = current_display_name or Path(tournament_path).stem
            tournaments.append((resolved_path, display_name))

    return tournaments


def main(
    base_path: Optional[str] = None,
    players_file: Optional[str] = None,
    tournaments: Optional[List[str]] = None,
    manifest: Optional[str] = None,
    output: str = './output',
    auto_init: bool = False,
    default_elo: float = DEFAULT_ELO,
    quiet: bool = False,
    use_cli_args: bool = True
) -> Optional['Elod']:
    """
    Main entry point for ELO calculation.

    Can be called directly with parameters or parse from command line.

    Args:
        base_path: Base path for relative file paths
        players_file: Initial player ratings file (inicio.elod format)
        tournaments: List of tournament files to process (.txt or .mdb)
        manifest: Path to manifest file listing tournaments in chronological order
        output: Output directory for results
        auto_init: Auto-initialize players from tournament files
        default_elo: Default starting ELO for new players
        quiet: Suppress progress output
        use_cli_args: If True, parse arguments from command line (ignores other params)

    Returns:
        Elod instance with processed results, or None if validation fails
    """
    if use_cli_args:
        import argparse

        parser = argparse.ArgumentParser(
            description='Calculate ELO ratings from tournament results (.txt or .mdb files)'
        )
        parser.add_argument(
            '--base-path', '-b',
            default=None,
            help='Base path for relative file paths'
        )
        parser.add_argument(
            '--players-file', '-p',
            default=None,
            help='Initial player ratings file (inicio.elod format)'
        )
        parser.add_argument(
            '--tournaments', '-t',
            nargs='+',
            help='Tournament files to process (.txt or .mdb)'
        )
        parser.add_argument(
            '--manifest', '-m',
            help='Manifest file listing tournaments in chronological order'
        )
        parser.add_argument(
            '--output', '-o',
            default='./output',
            help='Output directory for results'
        )
        parser.add_argument(
            '--auto-init',
            action='store_true',
            help='Auto-initialize players from tournament files'
        )
        parser.add_argument(
            '--default-elo',
            type=float,
            default=DEFAULT_ELO,
            help=f'Default starting ELO for new players (default: {DEFAULT_ELO})'
        )
        parser.add_argument(
            '--quiet', '-q',
            action='store_true',
            help='Suppress progress output'
        )
        parser.add_argument(
            '--check-names',
            action='store_true',
            help='Check for potential duplicate player names (different spellings/accents)'
        )
        parser.add_argument(
            '--aliases', '-a',
            help='Path to player name aliases file (to unify duplicate names)'
        )
        parser.add_argument(
            '--deceased', '-d',
            help='Path to file listing deceased players to exclude from rankings'
        )

        args = parser.parse_args()

        # Validate: need either tournaments or manifest
        if not args.tournaments and not args.manifest:
            parser.error("Either --tournaments or --manifest must be specified")

        # Validate: need either players file or auto-init
        if not args.players_file and not args.auto_init:
            parser.error("Either --players-file or --auto-init must be specified")

        base_path = args.base_path
        players_file = args.players_file
        output = args.output
        auto_init = args.auto_init
        default_elo = args.default_elo
        quiet = args.quiet
        check_names = args.check_names

        # Load player name aliases if provided
        aliases: Dict[str, str] = {}
        if args.aliases:
            alias_path = Path(args.aliases)
            if not alias_path.is_absolute() and base_path:
                alias_path = Path(base_path) / args.aliases
            if alias_path.exists():
                aliases = parse_aliases(str(alias_path))
                if not quiet:
                    print(f"Loaded {len(aliases)} name aliases from: {alias_path}")
            else:
                print(f"Warning: Alias file not found: {alias_path}")

        # Load deceased players list if provided
        deceased: Set[str] = set()
        if args.deceased:
            deceased_path = Path(args.deceased)
            if not deceased_path.is_absolute() and base_path:
                deceased_path = Path(base_path) / args.deceased
            if deceased_path.exists():
                deceased = load_deceased_players(str(deceased_path))
                if not quiet:
                    print(f"Loaded {len(deceased)} deceased players to exclude from: {deceased_path}")
            else:
                print(f"Warning: Deceased players file not found: {deceased_path}")

        # Get tournaments from manifest or command line
        if args.manifest:
            tournaments = parse_manifest(args.manifest, base_path)
            if not quiet:
                print(f"Loaded {len(tournaments)} tournaments from manifest: {args.manifest}")
        else:
            tournaments = args.tournaments
    else:
        # Direct parameter usage - validate
        check_names = False
        aliases = {}
        deceased = set()
        if manifest:
            tournaments = parse_manifest(manifest, base_path)
        if not tournaments:
            print("Error: Either tournaments list or manifest is required")
            return None
        if not players_file and not auto_init:
            print("Error: Either players_file or auto_init must be specified")
            return None

    elod = Elod(base_path=base_path)
    elod.deceased_players = deceased
    elod.run(
        players_file=players_file,
        tournament_files=tournaments,
        output_path=output,
        verbose=not quiet,
        auto_init_players=auto_init,
        default_elo=default_elo,
        aliases=aliases
    )

    if not quiet:
        # Filter out deceased players from rankings
        sorted_players = {k: v for k, v in elod.sort_players().items() if k not in deceased}
        if deceased:
            excluded_count = len(elod.players) - len(sorted_players)
            print(f"\nExcluded {excluded_count} deceased players from rankings")

        print("\nFinal Rankings:")
        print("-" * 140)
        print(f"{'Pos':>4}  {'Jugador':<25}  {'ELOD Ini':>8}  {'Delta':>7}  {'ELOD Fin':>8}  {'N.Opon':>6}  {'N.Part':>6}  {'Ultimo Torneo':<30}")
        print("-" * 140)
        for position, (name, player) in enumerate(sorted_players.items(), start=1):
            delta = player.delta_elo
            delta_str = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
            print(f"{position:>4}  {name:<25}  {player.initial_elo:>8.0f}  {delta_str:>7}  {player.elo:>8.0f}  {player.games:>6}  {player.tourneys:>6}  {player.last_torney:<30}")

    # Check for potential duplicate names
    if check_names:
        player_names = list(elod.players.keys())
        exact_duplicates, similar_pairs = find_similar_names(player_names)

        has_issues = exact_duplicates or similar_pairs

        if has_issues:
            print("\n" + "=" * 100)
            print("ADVERTENCIA: Posibles nombres duplicados detectados")
            print("=" * 100)

            if exact_duplicates:
                print("\n1. VARIACIONES DE ACENTOS (mismo nombre, diferente ortografía):")
                print("-" * 60)
                for normalized, variants in sorted(exact_duplicates.items()):
                    print(f"\n  '{normalized}':")
                    for variant in variants:
                        player = elod.players[variant]
                        print(f"    - {variant:<25} (ELOD: {player.elo:.0f}, Torneos: {player.tourneys})")

            if similar_pairs:
                print("\n\n2. NOMBRES SIMILARES (posibles apodos o errores tipográficos):")
                print("-" * 60)
                for name1, name2, distance in similar_pairs:
                    player1 = elod.players[name1]
                    player2 = elod.players[name2]
                    print(f"\n  '{name1}' vs '{name2}' (diferencia: {distance} caracteres):")
                    print(f"    - {name1:<25} (ELOD: {player1.elo:.0f}, Torneos: {player1.tourneys})")
                    print(f"    - {name2:<25} (ELOD: {player2.elo:.0f}, Torneos: {player2.tourneys})")

            print("\n" + "=" * 100)
            print("Considere unificar estos nombres en los archivos fuente.")
            print("=" * 100)
        else:
            print("\nNo se detectaron nombres duplicados.")

    return elod


if __name__ == '__main__':
    main()
