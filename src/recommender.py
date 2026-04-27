import csv
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Algorithm Recipe — point values for each feature (max total = 12.5 pts)
#
# Feature            Points    Why
# ─────────────────  ────────  ──────────────────────────────────────────────
# Mood match         +3.0      Most context-sensitive — listeners say "I want
#                              something chill NOW" even outside their genre
# Energy similarity  up to +4.0 Widest perceptual spread in dataset (0.22–0.97)
#                              Wrong energy feels immediately wrong
# Genre match        +1.0      Cultural identity — prevents jarring cross-genre
#                              surprises, but ranks below mood intentionally
# Valence similarity up to +1.5 Separates "fast-happy" from "fast-sad" —
#                              the edge case genre + energy alone can't catch
# Acousticness sim.  up to +0.5 Texture modifier (organic vs synthetic) —
#                              meaningful but rarely the deciding factor
# Popularity sim.    up to +1.0 Proximity to target mainstream level
# Release decade     up to +0.5 Stepped decay by era distance
# Mood intensity     up to +0.5 Proximity to desired emotional intensity
# Key match          +0.25     Exact match (major/minor)
# Complexity sim.    up to +0.25 Proximity to desired musical density
# ---------------------------------------------------------------------------
_POINTS = {
    "mood_match":         3.0,
    "energy_max":         4.0,
    "genre_match":        1.0,
    "valence_max":        1.5,
    "acoustic_max":       0.5,
    "popularity_max":     1.0,    # proximity to target mainstream level
    "decade_max":         0.5,    # stepped decay by era distance
    "mood_intensity_max": 0.5,    # proximity to desired emotional intensity
    "key_match":          0.25,   # exact match (major/minor)
    "complexity_max":     0.25,   # proximity to desired musical density
}

LOGGER = logging.getLogger(__name__)
NUMERIC_PROFILE_LIMITS = {
    "target_energy": (0.0, 1.0),
    "target_valence": (0.0, 1.0),
    "target_acousticness": (0.0, 1.0),
    "target_popularity": (0.0, 100.0),
    "target_mood_intensity": (0.0, 1.0),
    "target_complexity": (0.0, 1.0),
}
STABILITY_DELTAS = {
    "target_energy": 0.05,
    "target_valence": 0.05,
    "target_acousticness": 0.07,
    "target_popularity": 8.0,
    "target_mood_intensity": 0.06,
    "target_complexity": 0.06,
}
STABILITY_BONUS = 0.75


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Song:
    """Immutable record of a song and its audio feature attributes."""
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float
    # New columns added in the expanded dataset — defaulted so existing
    # test fixtures that omit them still construct successfully.
    speechiness: float = 0.0
    instrumentalness: float = 0.0
    liveness: float = 0.0
    popularity: int = 50
    release_decade: int = 2020
    mood_intensity: float = 0.5
    key: str = "major"
    complexity: float = 0.5


@dataclass
class UserProfile:
    """Stores a listener's taste preferences for content-based scoring."""
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool          # True → prefers acoustic; False → prefers synthetic


@dataclass
class ReliabilityReport:
    """Summary of recommendation stability and guardrail checks."""
    variant_count: int
    stable_recommendation_ratio: float
    average_stability: float
    low_stability_count: int
    warnings: List[str]


@dataclass
class RecommendationTrace:
    """Observable decision chain for one recommendation run."""
    normalized_prefs: Dict[str, Any]
    guardrail_warnings: List[str]
    variant_count: int
    top_candidates: List[Dict[str, Any]]


class RecommendationError(ValueError):
    """Raised when inputs cannot be safely processed."""


# ---------------------------------------------------------------------------
# Functional interface  (used by src/main.py)
# ---------------------------------------------------------------------------

def load_songs(csv_path: str) -> List[Dict]:
    """Parse a songs CSV file and return a list of dicts with typed numeric fields."""
    songs = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                songs.append({
                    "id":               int(row["id"]),
                    "title":            row["title"],
                    "artist":           row["artist"],
                    "genre":            row["genre"],
                    "mood":             row["mood"],
                    "energy":           float(row["energy"]),
                    "tempo_bpm":        float(row["tempo_bpm"]),
                    "valence":          float(row["valence"]),
                    "danceability":     float(row["danceability"]),
                    "acousticness":     float(row["acousticness"]),
                    "speechiness":      float(row.get("speechiness", 0.0)),
                    "instrumentalness": float(row.get("instrumentalness", 0.0)),
                    "liveness":         float(row.get("liveness", 0.0)),
                    "popularity":       int(row.get("popularity", 50)),
                    "release_decade":   int(row.get("release_decade", 2020)),
                    "mood_intensity":   float(row.get("mood_intensity", 0.5)),
                    "key":              row.get("key", "major"),
                    "complexity":       float(row.get("complexity", 0.5)),
                })
    except FileNotFoundError as exc:
        raise RecommendationError(f"Could not find song catalog at '{csv_path}'.") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise RecommendationError(f"Song catalog '{csv_path}' contains invalid data: {exc}") from exc

    if not songs:
        raise RecommendationError(f"Song catalog '{csv_path}' is empty.")

    LOGGER.info("Loaded %s songs from %s", len(songs), csv_path)
    return songs


def _clamp(value: float, lower: float, upper: float) -> float:
    """Keep numeric values inside inclusive bounds."""
    return max(lower, min(upper, value))


def validate_user_prefs(user_prefs: Dict[str, Any], songs: List[Dict]) -> List[str]:
    """Validate and normalize profile values in-place, returning any guardrail warnings."""
    if not isinstance(user_prefs, dict):
        raise RecommendationError("User preferences must be provided as a dictionary.")
    if not songs:
        raise RecommendationError("At least one song is required to generate recommendations.")

    warnings: List[str] = []
    for key, (lower, upper) in NUMERIC_PROFILE_LIMITS.items():
        if key not in user_prefs or user_prefs[key] is None:
            continue
        value = float(user_prefs[key])
        if value < lower or value > upper:
            clamped = _clamp(value, lower, upper)
            user_prefs[key] = clamped
            warning = f"{key} was outside {lower:.0f}-{upper:.0f} and was clamped to {clamped:.2f}."
            warnings.append(warning)
            LOGGER.warning(warning)

    catalog_genres = {song["genre"] for song in songs}
    catalog_moods = {song["mood"] for song in songs}
    target_genre = user_prefs.get("genre") or user_prefs.get("favorite_genre")
    target_mood = user_prefs.get("mood") or user_prefs.get("favorite_mood")

    if target_genre and target_genre not in catalog_genres:
        warnings.append(
            f"Requested genre '{target_genre}' is not in the catalog, so results will rely on mood and numeric similarity."
        )
    if target_mood and target_mood not in catalog_moods:
        warnings.append(
            f"Requested mood '{target_mood}' is not in the catalog, so exact mood matching is unavailable."
        )
    if (
        target_mood == "sad"
        and float(user_prefs.get("target_energy", 0.5)) > 0.85
    ):
        warnings.append(
            "Profile asks for a very high-energy sad track, which is rare in this catalog, so recommendations may be less stable."
        )

    return warnings


def _generate_stability_variants(user_prefs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create small profile perturbations used to test recommendation consistency."""
    variants = [dict(user_prefs)]
    for key, delta in STABILITY_DELTAS.items():
        if user_prefs.get(key) is None:
            continue
        lower, upper = NUMERIC_PROFILE_LIMITS[key]
        base_value = float(user_prefs[key])
        minus_variant = dict(user_prefs)
        plus_variant = dict(user_prefs)
        minus_variant[key] = _clamp(base_value - delta, lower, upper)
        plus_variant[key] = _clamp(base_value + delta, lower, upper)
        variants.extend([minus_variant, plus_variant])
    return variants


def _score_catalog(
    user_prefs: Dict[str, Any],
    songs: List[Dict],
    *,
    include_stability: bool,
    k: int,
) -> List[Dict[str, Any]]:
    """Score the full catalog and optionally blend in stability-based confidence."""
    base_rows = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        base_rows.append({
            "song": song,
            "score": score,
            "reasons": reasons,
            "stability": 1.0,
            "blended_score": score,
        })

    if not include_stability:
        return base_rows

    variants = _generate_stability_variants(user_prefs)
    appearances = {song["id"]: 0 for song in songs}
    for variant in variants:
        variant_rows = []
        for song in songs:
            variant_score, _ = score_song(variant, song)
            variant_rows.append((song["id"], variant_score))
        variant_rows.sort(key=lambda item: item[1], reverse=True)
        for song_id, _ in variant_rows[:k]:
            appearances[song_id] += 1

    variant_count = len(variants)
    for row in base_rows:
        stability = appearances[row["song"]["id"]] / variant_count
        row["stability"] = stability
        row["blended_score"] = row["score"] + (stability * STABILITY_BONUS)
        stability_label = "stable" if stability >= 0.7 else "watch closely"
        row["reasons"] = row["reasons"] + [
            f"reliability {stability_label} ({appearances[row['song']['id']]}/{variant_count} nearby profile checks)"
        ]

    return base_rows


def build_reliability_report(user_prefs: Dict[str, Any], songs: List[Dict], k: int = 5) -> ReliabilityReport:
    """Measure how robust the top-k results are under slight profile changes."""
    warnings = validate_user_prefs(dict(user_prefs), songs)
    scored_rows = _score_catalog(dict(user_prefs), songs, include_stability=True, k=k)
    ranked_rows = sorted(scored_rows, key=lambda item: item["blended_score"], reverse=True)[:k]

    if not ranked_rows:
        return ReliabilityReport(variant_count=0, stable_recommendation_ratio=0.0, average_stability=0.0, low_stability_count=0, warnings=warnings)

    variant_count = len(_generate_stability_variants(user_prefs))
    average_stability = sum(row["stability"] for row in ranked_rows) / len(ranked_rows)
    stable_count = sum(1 for row in ranked_rows if row["stability"] >= 0.7)
    low_stability_count = sum(1 for row in ranked_rows if row["stability"] < 0.5)
    if low_stability_count:
        warnings.append(
            f"{low_stability_count} recommendation(s) changed a lot during nearby-profile checks, so treat them as lower-confidence suggestions."
        )

    return ReliabilityReport(
        variant_count=variant_count,
        stable_recommendation_ratio=stable_count / len(ranked_rows),
        average_stability=average_stability,
        low_stability_count=low_stability_count,
        warnings=warnings,
    )


def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score one song against user preferences and return (total_pts, reasons_list). Max score = 12.5."""
    score = 0.0
    reasons = []

    # ── Mood (categorical, +3.0 on exact match) ───────────────────────────────
    target_mood = user_prefs.get("mood") or user_prefs.get("favorite_mood", "")
    if song["mood"] == target_mood:
        score += _POINTS["mood_match"]
        reasons.append(f"+{_POINTS['mood_match']:.1f} mood matches '{song['mood']}'")

    # ── Energy (proximity, up to +4.0) ────────────────────────────────────────
    target_energy = float(
        user_prefs.get("target_energy") if user_prefs.get("target_energy") is not None
        else user_prefs.get("energy", 0.5)
    )
    energy_pts = _POINTS["energy_max"] * (1.0 - abs(song["energy"] - target_energy))
    score += energy_pts
    reasons.append(
        f"+{energy_pts:.2f} energy similarity "
        f"(song {song['energy']:.2f}, target {target_energy:.2f})"
    )

    # ── Genre (categorical, +1.0 on exact match) ──────────────────────────────
    target_genre = user_prefs.get("genre") or user_prefs.get("favorite_genre", "")
    if song["genre"] == target_genre:
        score += _POINTS["genre_match"]
        reasons.append(f"+{_POINTS['genre_match']:.1f} genre matches '{song['genre']}'")

    # ── Valence (proximity, up to +1.5) ───────────────────────────────────────
    target_valence = float(user_prefs.get("target_valence", 0.65))
    valence_pts = _POINTS["valence_max"] * (1.0 - abs(song["valence"] - target_valence))
    score += valence_pts
    reasons.append(
        f"+{valence_pts:.2f} valence similarity "
        f"(song {song['valence']:.2f}, target {target_valence:.2f})"
    )

    # ── Acousticness (proximity, up to +0.5) ──────────────────────────────────
    # Accepts either a float target or the legacy bool from UserProfile.
    if user_prefs.get("target_acousticness") is not None:
        target_acoustic = float(user_prefs["target_acousticness"])
    else:
        target_acoustic = 0.8 if user_prefs.get("likes_acoustic") else 0.2
    acoustic_pts = _POINTS["acoustic_max"] * (1.0 - abs(song["acousticness"] - target_acoustic))
    score += acoustic_pts
    reasons.append(
        f"+{acoustic_pts:.2f} acousticness similarity "
        f"(song {song['acousticness']:.2f}, target {target_acoustic:.2f})"
    )

    # ── Popularity (proximity, up to +1.0) ────────────────────────────────────
    # target_popularity=80 → mainstream listener; target_popularity=20 → underground fan
    target_pop = float(user_prefs.get("target_popularity", 50))
    pop_pts = _POINTS["popularity_max"] * (1.0 - abs(song["popularity"] - target_pop) / 100.0)
    score += pop_pts
    reasons.append(
        f"+{pop_pts:.2f} popularity similarity "
        f"(song {song['popularity']}, target {int(target_pop)})"
    )

    # ── Release Decade (stepped, up to +0.5) ──────────────────────────────────
    # Each decade away from the target halves the remaining points.
    # Same decade → 0.5 pts; 1 decade off → 0.25 pts; 2 off → 0.125 pts; etc.
    target_decade = int(user_prefs.get("target_decade", 2020))
    decades_away = abs(song["release_decade"] - target_decade) // 10
    decade_pts = _POINTS["decade_max"] * (0.5 ** decades_away)
    score += decade_pts
    reasons.append(
        f"+{decade_pts:.2f} release era "
        f"(song {song['release_decade']}, target {target_decade})"
    )

    # ── Mood Intensity (proximity, up to +0.5) ────────────────────────────────
    # Separates subtle expressions from overwhelming ones within the same mood label.
    target_intensity = float(user_prefs.get("target_mood_intensity", 0.5))
    intensity_pts = _POINTS["mood_intensity_max"] * (1.0 - abs(song["mood_intensity"] - target_intensity))
    score += intensity_pts
    reasons.append(
        f"+{intensity_pts:.2f} mood intensity "
        f"(song {song['mood_intensity']:.2f}, target {target_intensity:.2f})"
    )

    # ── Key (categorical, +0.25 on exact match) ───────────────────────────────
    # Major keys sound brighter/resolved; minor keys sound darker/tense.
    target_key = user_prefs.get("target_key", "")
    if target_key and song["key"] == target_key:
        score += _POINTS["key_match"]
        reasons.append(f"+{_POINTS['key_match']:.2f} key matches '{song['key']}'")

    # ── Complexity (proximity, up to +0.25) ───────────────────────────────────
    # Separates minimalist loops from intricate, layered arrangements.
    target_complexity = float(user_prefs.get("target_complexity", 0.5))
    complexity_pts = _POINTS["complexity_max"] * (1.0 - abs(song["complexity"] - target_complexity))
    score += complexity_pts
    reasons.append(
        f"+{complexity_pts:.2f} complexity "
        f"(song {song['complexity']:.2f}, target {target_complexity:.2f})"
    )

    return round(score, 4), reasons


def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score every song, sort by score descending, and return the top-k (song, score, explanation) tuples."""
    if k <= 0:
        raise RecommendationError("k must be at least 1.")

    normalized_prefs = dict(user_prefs)
    guardrail_warnings = validate_user_prefs(normalized_prefs, songs)
    scored_rows = _score_catalog(normalized_prefs, songs, include_stability=True, k=k)
    scored_rows.sort(key=lambda item: item["blended_score"], reverse=True)

    results = []
    for rank, row in enumerate(scored_rows[:k], start=1):
        explanation_parts = list(row["reasons"])
        if rank == 1:
            explanation_parts.extend([f"guardrail: {warning}" for warning in guardrail_warnings])
        explanation = " | ".join(explanation_parts)
        results.append((row["song"], row["score"], explanation))

    LOGGER.info(
        "Generated %s recommendations for genre=%s mood=%s",
        len(results),
        normalized_prefs.get("genre") or normalized_prefs.get("favorite_genre"),
        normalized_prefs.get("mood") or normalized_prefs.get("favorite_mood"),
    )
    return results


def trace_recommendation_pipeline(user_prefs: Dict, songs: List[Dict], k: int = 5) -> RecommendationTrace:
    """Return an observable reasoning trace for the top recommendation candidates."""
    if k <= 0:
        raise RecommendationError("k must be at least 1.")

    normalized_prefs = dict(user_prefs)
    guardrail_warnings = validate_user_prefs(normalized_prefs, songs)
    scored_rows = _score_catalog(normalized_prefs, songs, include_stability=True, k=k)
    scored_rows.sort(key=lambda item: item["blended_score"], reverse=True)

    top_candidates = []
    for row in scored_rows[:k]:
        top_candidates.append({
            "title": row["song"]["title"],
            "artist": row["song"]["artist"],
            "base_score": row["score"],
            "stability": row["stability"],
            "blended_score": row["blended_score"],
            "reason_count": len(row["reasons"]),
            "reasons": list(row["reasons"]),
        })

    return RecommendationTrace(
        normalized_prefs=normalized_prefs,
        guardrail_warnings=guardrail_warnings,
        variant_count=len(_generate_stability_variants(normalized_prefs)),
        top_candidates=top_candidates,
    )


# ---------------------------------------------------------------------------
# OOP interface  (used by tests/test_recommender.py)
# ---------------------------------------------------------------------------

class Recommender:
    """
    OOP wrapper around the functional scoring logic.
    Required by tests/test_recommender.py
    """

    def __init__(self, songs: List[Song]):
        """Store the song catalog for repeated recommendation calls."""
        self.songs = songs

    def _profile_to_dict(self, user: UserProfile) -> Dict:
        """Converts a UserProfile dataclass into a dict for score_song()."""
        return {
            "genre":                  user.favorite_genre,
            "mood":                   user.favorite_mood,
            "target_energy":          user.target_energy,
            "target_acousticness":    0.8 if user.likes_acoustic else 0.2,
            "target_popularity":      50,
            "target_decade":          2020,
            "target_mood_intensity":  0.5,
            "target_key":             "",
            "target_complexity":      0.5,
        }

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Returns the top-k Song objects sorted by descending score."""
        user_dict = self._profile_to_dict(user)
        scored = []
        for song in self.songs:
            song_dict = {
                "genre":            song.genre,
                "mood":             song.mood,
                "energy":           song.energy,
                "valence":          song.valence,
                "acousticness":     song.acousticness,
                "speechiness":      song.speechiness,
                "instrumentalness": song.instrumentalness,
                "liveness":         song.liveness,
                "popularity":       song.popularity,
                "release_decade":   song.release_decade,
                "mood_intensity":   song.mood_intensity,
                "key":              song.key,
                "complexity":       song.complexity,
            }
            score, _ = score_song(user_dict, song_dict)
            scored.append((song, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [song for song, _ in scored[:k]]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Returns a plain-language explanation of why song was recommended."""
        user_dict = self._profile_to_dict(user)
        song_dict = {
            "genre":            song.genre,
            "mood":             song.mood,
            "energy":           song.energy,
            "valence":          song.valence,
            "acousticness":     song.acousticness,
            "speechiness":      song.speechiness,
            "instrumentalness": song.instrumentalness,
            "liveness":         song.liveness,
            "popularity":       song.popularity,
            "release_decade":   song.release_decade,
            "mood_intensity":   song.mood_intensity,
            "key":              song.key,
            "complexity":       song.complexity,
        }
        _, reasons = score_song(user_dict, song_dict)
        return " | ".join(reasons)
