"""Evaluation harness for the reliability-aware music recommender."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from profiles import PROFILES  # noqa: E402
from recommender import (  # noqa: E402
    build_reliability_report,
    load_songs,
    recommend_songs,
    trace_recommendation_pipeline,
)

EVAL_CASES = [
    {
        "profile": "high_energy_pop",
        "expected_top_title": "Sunrise City",
        "min_average_stability": 0.85,
    },
    {
        "profile": "chill_lofi",
        "expected_top_title": "Midnight Coding",
        "min_average_stability": 0.85,
    },
    {
        "profile": "ghost_genre",
        "expected_top_title": "Library Rain",
        "min_average_stability": 0.85,
        "expect_warning_substring": "not in the catalog",
    },
    {
        "profile": "sad_banger",
        "expected_top_title": "Iron Cathedral",
        "min_average_stability": 0.70,
        "expect_warning_substring": "very high-energy sad track",
    },
]


def main() -> int:
    songs = load_songs(str(ROOT / "data" / "songs.csv"))
    passed = 0

    print("Reliability-Aware Evaluation Harness")
    print("=" * 60)

    for case in EVAL_CASES:
        profile_name = case["profile"]
        prefs = PROFILES[profile_name]
        recommendations = recommend_songs(prefs, songs, k=5)
        report = build_reliability_report(prefs, songs, k=5)
        trace = trace_recommendation_pipeline(prefs, songs, k=3)

        top_song = recommendations[0][0]["title"]
        title_ok = top_song == case["expected_top_title"]
        stability_ok = report.average_stability >= case["min_average_stability"]
        warning_ok = True
        expected_warning = case.get("expect_warning_substring")
        if expected_warning:
            warning_ok = any(expected_warning in warning for warning in report.warnings)

        case_passed = title_ok and stability_ok and warning_ok
        if case_passed:
            passed += 1

        print(f"\nProfile: {profile_name}")
        print(f"  Top recommendation     : {top_song}")
        print(f"  Average stability      : {report.average_stability:.0%}")
        print(f"  Stable top-5 ratio     : {report.stable_recommendation_ratio:.0%}")
        print(f"  Observable steps       : {trace.variant_count} nearby-profile checks, {len(trace.top_candidates)} traced candidates")
        print(f"  Guardrail warnings     : {len(report.warnings)}")
        print(f"  Result                 : {'PASS' if case_passed else 'FAIL'}")

    print("\n" + "=" * 60)
    print(f"Summary: {passed} out of {len(EVAL_CASES)} evaluation cases passed.")
    return 0 if passed == len(EVAL_CASES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
