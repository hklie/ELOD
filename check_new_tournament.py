#!/usr/bin/env python3
"""
Pre-flight QC for a newly added tournament — run BEFORE regenerate_all.py.

For each new tournament file it:
  1. Resolves every roster name through the alias table.
  2. Flags duplicates and likely errors:
       - the same player listed twice in the roster (after alias resolution)
       - a "new" name that is suspiciously close to an existing player
         (accent/spelling variant or missing alias -> would split one player in two)
  3. Lists genuinely NEW players (first-ever appearance) and warns if any
     are missing a country assignment.
  4. Prints a before/after ELO preview for the roster and the top of the table.

It NEVER writes output/elod_progresivos.xlsx — it only reports. Once the report
is clean, run `python regenerate_all.py` to actually update the ELOs.

Usage:
    python check_new_tournament.py                      # auto-detect new files
    python check_new_tournament.py data/2026/Foo.txt    # check specific file(s)

Exit code is non-zero if any blocking ERROR is found (so it can gate CI/scripts).
"""
import argparse
import contextlib
import io
import sys
from pathlib import Path

from elod import (
    Elod, parse_aliases, apply_aliases, parse_manifest,
    normalize_name, levenshtein_distance,
)
from generate_progressive import (
    ProgressiveElod, load_country_data, load_display_names,
)
from regenerate_all import find_year_manifests, parse_year_manifest

DATA = Path("data")
ALIAS = DATA / "jugadores_all.alias"
COUNTRY = DATA / "jugadores_pais.txt"
DISPLAY = DATA / "nombres_display.txt"
DECEASED = DATA / "jugadores_fallecidos.txt"
COMBINED = DATA / "torneos_all.manifiesto"

# How close (edit distance on accent-stripped names) before we warn about a
# possible accidental duplicate / missing alias.
SIMILARITY_MAX_DISTANCE = 2


def detect_new_files():
    """Tournament files present in a year manifest but not yet in the combined one."""
    processed = set()
    if COMBINED.exists():
        for filepath, _ in parse_manifest(str(COMBINED), str(DATA)):
            processed.add(Path(filepath).name)
    new = []
    for year, mpath in find_year_manifests(DATA):
        for line in parse_year_manifest(year, mpath):
            line = line.strip()
            if "/" not in line:  # blank, comment, or date line (file lines are "YYYY/<file>")
                continue
            candidate = DATA / line  # line is "YYYY/<file>"
            if candidate.name not in processed and candidate.exists():
                new.append(candidate)
    return new


def load_roster(path, aliases):
    """Return (raw_names, canonical_names) for a tournament file (any supported type)."""
    elod = Elod()
    with contextlib.redirect_stdout(io.StringIO()):
        data = elod.load_tournament(str(path))
    raw = list(data.all_players)
    canonical = [apply_aliases(n, aliases) for n in raw]
    return raw, canonical


def process(manifest_path):
    prog = ProgressiveElod()
    with contextlib.redirect_stdout(io.StringIO()):
        prog.process_tournaments(
            manifest_path=str(manifest_path),
            alias_path=str(ALIAS),
            base_path=str(DATA),
            deceased_path=str(DECEASED) if DECEASED.exists() else None,
            display_names_path=str(DISPLAY) if DISPLAY.exists() else None,
            country_path=str(COUNTRY) if COUNTRY.exists() else None,
        )
    return prog


def build_manifest(out_path, exclude_names=None):
    """Write a combined manifest from all year manifests, optionally excluding files."""
    exclude_names = exclude_names or set()
    lines = ["# preview", ""]
    for year, mpath in find_year_manifests(DATA):
        lines.append(f"# === {year} ===")
        for ln in parse_year_manifest(year, mpath):
            stripped = ln.strip()
            # file lines are "YYYY/<file>"; date/comment lines have no "/"
            if "/" in stripped and Path(stripped).name in exclude_names:
                continue  # drop this tournament file from the "before" view
            lines.append(ln)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="QC a new tournament before updating ELOs")
    ap.add_argument("files", nargs="*", help="Tournament file(s) to check (default: auto-detect)")
    args = ap.parse_args()

    aliases = parse_aliases(str(ALIAS))
    countries = load_country_data(str(COUNTRY))
    display = load_display_names(str(DISPLAY))

    def show(n):
        return display.get(n, n)

    files = [Path(f) for f in args.files] if args.files else detect_new_files()
    if not files:
        print("No new tournament files detected (all year-manifest files are already "
              "in torneos_all.manifiesto). Pass a file explicitly to force a check.")
        return 0

    print(f"Checking {len(files)} new tournament file(s): "
          f"{', '.join(f.name for f in files)}\n")

    # Baseline = everything EXCEPT the files under review.
    check_names = {f.name for f in files}
    before_mf = DATA / "_qc_before.manifiesto"
    after_mf = DATA / "_qc_after.manifiesto"
    build_manifest(before_mf, exclude_names=check_names)
    build_manifest(after_mf)

    before = process(before_mf)
    after = process(after_mf)
    before_mf.unlink(missing_ok=True)
    after_mf.unlink(missing_ok=True)

    existing = set(before.players)             # canonical players known before these files
    existing_norm = {normalize_name(n): n for n in existing}

    before_elo = {n: p.elo for n, p in before.players.items()}
    after_rank = sorted(
        ((n, p.elo) for n, p in after.players.items() if n not in after.deceased_players),
        key=lambda x: x[1], reverse=True,
    )
    before_rank = sorted(
        ((n, p.elo) for n, p in before.players.items() if n not in before.deceased_players),
        key=lambda x: x[1], reverse=True,
    )

    errors, warnings = [], []
    all_new_players = []

    for f in files:
        raw, canonical = load_roster(f, aliases)
        print("=" * 80)
        print(f"ROSTER: {f.name}  ({len(canonical)} players)")
        print("=" * 80)

        # 1) duplicate canonical within this roster
        seen = {}
        for r, c in zip(raw, canonical):
            seen.setdefault(c, []).append(r)
        for c, sources in seen.items():
            if len(sources) > 1:
                errors.append(f"[{f.name}] '{show(c)}' listed {len(sources)}x "
                              f"in roster (raw: {', '.join(sources)})")

        # 2) per-player status + similarity check
        new_players = []
        for c in dict.fromkeys(canonical):     # de-dup, keep order
            if c in existing:
                continue
            new_players.append(c)
            # is this "new" name suspiciously close to an existing player?
            cn = normalize_name(c)
            if cn in existing_norm and existing_norm[cn] != c:
                errors.append(f"[{f.name}] '{show(c)}' is an accent/case variant of "
                              f"existing player '{show(existing_norm[cn])}' "
                              f"-> add an alias to avoid a duplicate")
                continue
            close = [
                e for e in existing
                if 0 < levenshtein_distance(cn, normalize_name(e)) <= SIMILARITY_MAX_DISTANCE
            ]
            for e in close:
                warnings.append(f"[{f.name}] NEW '{show(c)}' is very similar to existing "
                                f"'{show(e)}' (check for typo / missing alias)")

        # 3) report roster with before/after
        print(f"{'Player':30} {'Status':9} {'ELO before':>10} {'ELO after':>10} {'Δ':>7}")
        print("-" * 80)
        for c in dict.fromkeys(canonical):
            is_new = c not in existing
            eb = before_elo.get(c)
            ea = after.players[c].elo if c in after.players else None
            eb_s = f"{eb:.0f}" if eb is not None else "—"
            ea_s = f"{ea:.0f}" if ea is not None else "?"
            d_s = (f"{ea-eb:+.0f}" if eb is not None and ea is not None
                   else ("NEW" if is_new else ""))
            print(f"{show(c):30} {'NEW' if is_new else 'existing':9} "
                  f"{eb_s:>10} {ea_s:>10} {d_s:>7}")

        # 4) missing-country check for new players
        for c in new_players:
            if c not in countries:
                warnings.append(f"[{f.name}] NEW player '{show(c)}' has no country in "
                                f"{COUNTRY.name}")
        all_new_players.extend(new_players)
        print()

    # New-player summary
    print("=" * 80)
    print(f"NEW PLAYERS (first-ever appearance): {len(all_new_players)}")
    print("=" * 80)
    for c in all_new_players:
        print(f"  • {show(c):30} country: {countries.get(c, '(none set)')}")
    print()

    # Top-15 before/after
    print("=" * 80)
    print("TOP 15  —  BEFORE vs AFTER")
    print("=" * 80)
    print(f"{'#':>3}  {'BEFORE':28} {'ELO':>6}    {'#':>3}  {'AFTER':28} {'ELO':>6}")
    print("-" * 80)
    for i in range(min(15, len(after_rank))):
        bn, be = before_rank[i] if i < len(before_rank) else ("—", 0)
        an, ae = after_rank[i]
        mark = "" if (i < len(before_rank) and an == bn) else "  <-"
        be_s = f"{be:.0f}" if i < len(before_rank) else ""
        print(f"{i+1:>3}  {show(bn):28} {be_s:>6}    {i+1:>3}  {show(an):28} {ae:>6.0f}{mark}")
    print()
    print(f"Total players  BEFORE: {len(before_rank)}   AFTER: {len(after_rank)}   "
          f"(+{len(after_rank)-len(before_rank)})")
    print()

    # Verdict
    print("=" * 80)
    if errors:
        print(f"❌ {len(errors)} ERROR(S) — fix before regenerating:")
        for e in errors:
            print(f"   ERROR: {e}")
    if warnings:
        print(f"⚠️  {len(warnings)} WARNING(S) — please review:")
        for w in warnings:
            print(f"   WARN:  {w}")
    if not errors and not warnings:
        print("✅ All checks passed. Safe to run: python regenerate_all.py")
    elif not errors:
        print("\n✅ No blocking errors. Review warnings, then: python regenerate_all.py")
    print("=" * 80)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
