"""
Command line runner for the Music Recommender Simulation.

Usage:
    python src/main.py                      # runs ACTIVE_PROFILE
    python src/main.py <profile_name>       # runs a named profile
    python src/main.py --list               # prints all available profiles
"""

import logging
import sys
from recommender import (
    RecommendationError,
    build_reliability_report,
    load_songs,
    recommend_songs,
)

# ---------------------------------------------------------------------------
# Standard profiles — coherent, expected taste shapes
# ---------------------------------------------------------------------------

PROFILES = {

    # ── Standard profiles ────────────────────────────────────────────────────

    "high_energy_pop": {
        "genre":                  "pop",
        "mood":                   "happy",
        "target_energy":          0.90,
        "target_valence":         0.85,
        "target_acousticness":    0.08,
        "target_popularity":      82,
        "target_decade":          2020,
        "target_mood_intensity":  0.82,
        "target_key":             "major",
        "target_complexity":      0.45,
    },
    "chill_lofi": {
        "genre":                  "lofi",
        "mood":                   "chill",
        "target_energy":          0.38,
        "target_valence":         0.58,
        "target_acousticness":    0.80,
        "target_popularity":      45,
        "target_decade":          2020,
        "target_mood_intensity":  0.50,
        "target_key":             "minor",
        "target_complexity":      0.28,
    },
    "deep_intense_rock": {
        "genre":                  "rock",
        "mood":                   "intense",
        "target_energy":          0.92,
        "target_valence":         0.45,
        "target_acousticness":    0.10,
        "target_popularity":      60,
        "target_decade":          2010,
        "target_mood_intensity":  0.90,
        "target_key":             "minor",
        "target_complexity":      0.72,
    },

    # ── Adversarial / edge-case profiles ─────────────────────────────────────
    # These are designed to expose weaknesses in the scoring logic.

    "sad_banger": {
        # Contradiction: mood=sad expects low energy, but energy=0.92 is near max.
        # Also targets metal genre, but no metal song has mood=sad.
        # Exposes: can the scorer serve both signals at once, or does one cancel out?
        "genre":                  "metal",
        "mood":                   "sad",
        "target_energy":          0.92,
        "target_valence":         0.25,
        "target_acousticness":    0.08,
        "target_popularity":      55,
        "target_decade":          2010,
        "target_mood_intensity":  0.95,
        "target_key":             "minor",
        "target_complexity":      0.80,
    },
    "ghost_genre": {
        # Genre "bluegrass" does not exist in the catalog — genre match is
        # permanently unavailable (always 0 pts). The ranking falls entirely
        # to mood + numerical proximity, revealing what the scorer does without
        # its second-highest categorical signal.
        "genre":                  "bluegrass",
        "mood":                   "chill",
        "target_energy":          0.35,
        "target_valence":         0.62,
        "target_acousticness":    0.80,
        "target_popularity":      40,
        "target_decade":          2020,
        "target_mood_intensity":  0.42,
        "target_key":             "major",
        "target_complexity":      0.25,
    },
    "neutral_listener": {
        # All numerical targets are at 0.5 — the exact midpoint of every scale.
        # No song is very close OR very far on any numerical feature.
        # Only categorical matches (mood, genre) can create meaningful separation.
        # Exposes: does the system produce a sensible ranking on sparse signal?
        "genre":                  "ambient",
        "mood":                   "relaxed",
        "target_energy":          0.50,
        "target_valence":         0.65,
        "target_acousticness":    0.50,
        "target_popularity":      50,
        "target_decade":          2020,
        "target_mood_intensity":  0.50,
        "target_key":             "",
        "target_complexity":      0.50,
    },

    # ── Previously defined profiles ──────────────────────────────────────────

    "pop_happy": {
        "genre":                  "pop",
        "mood":                   "happy",
        "target_energy":          0.80,
        "target_valence":         0.84,
        "target_acousticness":    0.18,
        "target_popularity":      80,
        "target_decade":          2020,
        "target_mood_intensity":  0.78,
        "target_key":             "major",
        "target_complexity":      0.42,
    },
    "study": {
        "genre":                  "lofi",
        "mood":                   "focused",
        "target_energy":          0.40,
        "target_valence":         0.58,
        "target_acousticness":    0.75,
        "target_popularity":      40,
        "target_decade":          2020,
        "target_mood_intensity":  0.58,
        "target_key":             "minor",
        "target_complexity":      0.26,
    },
    "workout": {
        "genre":                  "pop",
        "mood":                   "intense",
        "target_energy":          0.92,
        "target_valence":         0.77,
        "target_acousticness":    0.05,
        "target_popularity":      85,
        "target_decade":          2020,
        "target_mood_intensity":  0.93,
        "target_key":             "major",
        "target_complexity":      0.50,
    },
    "night_drive": {
        "genre":                  "synthwave",
        "mood":                   "moody",
        "target_energy":          0.76,
        "target_valence":         0.49,
        "target_acousticness":    0.20,
        "target_popularity":      58,
        "target_decade":          2010,
        "target_mood_intensity":  0.76,
        "target_key":             "minor",
        "target_complexity":      0.55,
    },
    "hiphop": {
        "genre":                  "hip-hop",
        "mood":                   "confident",
        "target_energy":          0.85,
        "target_valence":         0.72,
        "target_acousticness":    0.06,
        "target_popularity":      80,
        "target_decade":          2020,
        "target_mood_intensity":  0.85,
        "target_key":             "minor",
        "target_complexity":      0.60,
    },
}

ACTIVE_PROFILE = "high_energy_pop"

WIDTH = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)


def print_header(profile_name: str, prefs: dict) -> None:
    """Print the profile banner."""
    print("=" * WIDTH)
    print("  Music Recommender Simulation")
    print(f"  Profile : {profile_name}")
    print(f"  genre={prefs['genre']}  |  mood={prefs['mood']}  |  energy={prefs['target_energy']}")
    print("=" * WIDTH)


def print_recommendation(rank: int, song: dict, score: float, explanation: str) -> None:
    """Print one ranked result with its per-feature reasons."""
    print(f"\n  #{rank}  {song['title']}  —  {song['artist']}")
    print(f"       Score : {score:.2f} / 12.5 pts")
    print(f"       Why   :")
    for reason in explanation.split(" | "):
        print(f"         {reason}")


def print_reliability_summary(report) -> None:
    """Print the integrated recommendation reliability audit."""
    print("\n  Reliability Audit\n" + "-" * WIDTH)
    print(f"  Nearby profile checks run : {report.variant_count}")
    print(f"  Stable top-5 ratio        : {report.stable_recommendation_ratio:.0%}")
    print(f"  Average recommendation stability : {report.average_stability:.0%}")
    if report.warnings:
        print("  Guardrails:")
        for warning in report.warnings:
            print(f"    - {warning}")


def run_profile(profile_name: str, songs: list) -> None:
    """Load a profile, score all songs, and print the top-5 ranking."""
    if profile_name not in PROFILES:
        print(f"Unknown profile '{profile_name}'. Use --list to see options.")
        sys.exit(1)

    user_prefs = PROFILES[profile_name]
    print_header(profile_name, user_prefs)

    recommendations = recommend_songs(user_prefs, songs, k=5)
    reliability_report = build_reliability_report(user_prefs, songs, k=5)

    print(f"\n  Top {len(recommendations)} Recommendations\n" + "-" * WIDTH)
    for rank, (song, score, explanation) in enumerate(recommendations, start=1):
        print_recommendation(rank, song, score, explanation)

    print_reliability_summary(reliability_report)
    print("\n" + "=" * WIDTH)


def main() -> None:
    """Entry point — selects profile from argv or falls back to ACTIVE_PROFILE."""
    try:
        songs = load_songs("data/songs.csv")
        print(f"Loaded songs: {len(songs)}\n")

        if len(sys.argv) > 1:
            arg = sys.argv[1]
            if arg == "--list":
                print("Available profiles:")
                for name in PROFILES:
                    p = PROFILES[name]
                    print(f"  {name:<22} genre={p['genre']}, mood={p['mood']}")
                sys.exit(0)
            run_profile(arg, songs)
        else:
            run_profile(ACTIVE_PROFILE, songs)
    except RecommendationError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
