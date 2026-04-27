"""
Command line runner for the Music Recommender Simulation.

Usage:
    python src/main.py                      # runs ACTIVE_PROFILE
    python src/main.py <profile_name>       # runs a named profile
    python src/main.py --list               # prints all available profiles
    python src/main.py --trace <profile>    # prints intermediate scoring steps
"""

import logging
import sys
from recommender import (
    RecommendationError,
    build_reliability_report,
    load_songs,
    recommend_songs,
    trace_recommendation_pipeline,
)
from profiles import ACTIVE_PROFILE, PROFILES

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


def print_trace(profile_name: str, songs: list) -> None:
    """Print the intermediate reasoning chain for a recommendation run."""
    trace = trace_recommendation_pipeline(PROFILES[profile_name], songs, k=5)
    print_header(profile_name, trace.normalized_prefs)
    print("\n  Decision Trace\n" + "-" * WIDTH)
    print(f"  Normalized profile fields : {len(trace.normalized_prefs)}")
    print(f"  Nearby profile variants   : {trace.variant_count}")
    if trace.guardrail_warnings:
        print("  Guardrail warnings:")
        for warning in trace.guardrail_warnings:
            print(f"    - {warning}")
    print("\n  Top candidate chain")
    for rank, candidate in enumerate(trace.top_candidates, start=1):
        print(f"    {rank}. {candidate['title']} — {candidate['artist']}")
        print(
            "       "
            f"base={candidate['base_score']:.2f}  "
            f"stability={candidate['stability']:.0%}  "
            f"blended={candidate['blended_score']:.2f}"
        )
        for reason in candidate["reasons"][:4]:
            print(f"       {reason}")


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
            if arg == "--trace":
                if len(sys.argv) < 3:
                    print("Usage: python src/main.py --trace <profile_name>")
                    sys.exit(1)
                trace_profile = sys.argv[2]
                if trace_profile not in PROFILES:
                    print(f"Unknown profile '{trace_profile}'. Use --list to see options.")
                    sys.exit(1)
                print_trace(trace_profile, songs)
                sys.exit(0)
            run_profile(arg, songs)
        else:
            run_profile(ACTIVE_PROFILE, songs)
    except RecommendationError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
