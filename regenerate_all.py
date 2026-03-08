#!/usr/bin/env python3
"""
Regenerate all ELOD files from year-specific manifests.

This script:
1. Reads all year-specific manifests (data/YYYY/torneos_YYYY.manifiesto)
2. Generates the combined manifest (data/torneos_all.manifiesto)
3. Regenerates elod_progresivos.xlsx (consolidated output with all data)
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

from generate_progressive import ProgressiveElod


def find_year_manifests(data_path: Path) -> List[Tuple[int, Path]]:
    """Find all year-specific manifest files, sorted by year."""
    manifests = []
    for year_dir in data_path.iterdir():
        if year_dir.is_dir() and year_dir.name.isdigit():
            year = int(year_dir.name)
            manifest_path = year_dir / f"torneos_{year}.manifiesto"
            if manifest_path.exists():
                manifests.append((year, manifest_path))
    return sorted(manifests, key=lambda x: x[0])


def parse_year_manifest(year: int, manifest_path: Path) -> List[str]:
    """
    Parse a year manifest and return lines with year prefix added to file paths.
    """
    lines = []
    current_date_line = None
    last_was_blank = False

    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip('\n').strip()

            # Skip comments
            if stripped.startswith('#'):
                continue

            # Handle empty lines - only add one blank line between tournaments
            if not stripped:
                if lines and not last_was_blank:
                    lines.append('')
                    last_was_blank = True
                continue

            last_was_blank = False

            # Check if this is a date line (DD-MM-YYYY)
            if re.match(r'^\d{1,2}-\d{2}-\d{4}', stripped):
                current_date_line = stripped
                lines.append(stripped)
            else:
                # This is a file path - prepend year folder
                lines.append(f"{year}/{stripped}")

    # Remove trailing blank lines
    while lines and lines[-1] == '':
        lines.pop()

    return lines


def generate_combined_manifest(data_path: Path, output_path: Path) -> int:
    """
    Generate the combined manifest from all year manifests.
    Returns the number of tournament files found.
    """
    year_manifests = find_year_manifests(data_path)

    if not year_manifests:
        print("Error: No year manifests found")
        return 0

    all_lines = [
        "# Todos los Torneos - Generado automáticamente desde manifiestos por año",
        "# Formato: Fechas se especifican como DD-MM-YYYY seguido por el nombre del evento despues del caracter #",
        ""
    ]

    file_count = 0

    for year, manifest_path in year_manifests:
        all_lines.append(f"# === {year} ===")
        year_lines = parse_year_manifest(year, manifest_path)

        for line in year_lines:
            all_lines.append(line)
            # Count tournament files (non-empty, non-date, non-comment lines)
            if line and not line.startswith('#') and not re.match(r'^\d{1,2}-\d{2}-\d{4}', line):
                file_count += 1

        all_lines.append("")  # Blank line between years

    # Write combined manifest
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_lines))

    print(f"Generated {output_path}")
    print(f"  Years: {[y for y, _ in year_manifests]}")
    print(f"  Tournament files: {file_count}")

    return file_count


def run_elod_processing(data_path: Path, output_path: Path):
    """Run the ELOD processing scripts."""
    manifest = data_path / "torneos_all.manifiesto"
    aliases = data_path / "jugadores_all.alias"
    deceased = data_path / "jugadores_fallecidos.txt"
    display_names = data_path / "nombres_display.txt"
    country = data_path / "jugadores_pais.txt"

    # Generate elod_progresivos.xlsx (consolidated output with all data)
    print("\nGenerating elod_progresivos.xlsx...", flush=True)
    prog = ProgressiveElod()
    prog.process_tournaments(
        manifest_path=str(manifest),
        alias_path=str(aliases) if aliases.exists() else None,
        base_path=str(data_path),
        deceased_path=str(deceased) if deceased.exists() else None,
        display_names_path=str(display_names) if display_names.exists() else None,
        country_path=str(country) if country.exists() else None,
    )
    prog.generate_excel(str(output_path / "elod_progresivos.xlsx"))

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Regenerate all ELOD files from year-specific manifests'
    )
    parser.add_argument(
        '--data-path', '-d',
        default='data',
        help='Path to data directory (default: data)'
    )
    parser.add_argument(
        '--output-path', '-o',
        default='output',
        help='Path to output directory (default: output)'
    )
    parser.add_argument(
        '--manifest-only',
        action='store_true',
        help='Only regenerate the combined manifest, skip ELOD processing'
    )

    args = parser.parse_args()

    data_path = Path(args.data_path)
    output_path = Path(args.output_path)

    if not data_path.exists():
        print(f"Error: Data path not found: {data_path}")
        sys.exit(1)

    output_path.mkdir(parents=True, exist_ok=True)

    # Generate combined manifest
    print("=== Generating combined manifest ===")
    combined_manifest = data_path / "torneos_all.manifiesto"
    file_count = generate_combined_manifest(data_path, combined_manifest)

    if file_count == 0:
        sys.exit(1)

    if args.manifest_only:
        print("\nManifest generated. Skipping ELOD processing (--manifest-only)")
        return

    # Run ELOD processing
    print("\n=== Processing ELOD ===")
    if run_elod_processing(data_path, output_path):
        print("\n=== Complete ===")
        print(f"Output files in: {output_path}/")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
