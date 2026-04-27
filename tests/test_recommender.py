import pytest

from src.recommender import (
    RecommendationError,
    Recommender,
    Song,
    UserProfile,
    build_reliability_report,
    recommend_songs,
)

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


def test_recommend_songs_includes_reliability_signal_in_explanations():
    songs = [
        {
            "id": 1,
            "title": "Test Pop Track",
            "artist": "Test Artist",
            "genre": "pop",
            "mood": "happy",
            "energy": 0.8,
            "tempo_bpm": 120,
            "valence": 0.9,
            "danceability": 0.8,
            "acousticness": 0.2,
            "speechiness": 0.0,
            "instrumentalness": 0.0,
            "liveness": 0.1,
            "popularity": 80,
            "release_decade": 2020,
            "mood_intensity": 0.8,
            "key": "major",
            "complexity": 0.4,
        },
        {
            "id": 2,
            "title": "Chill Lofi Loop",
            "artist": "Test Artist",
            "genre": "lofi",
            "mood": "chill",
            "energy": 0.4,
            "tempo_bpm": 80,
            "valence": 0.6,
            "danceability": 0.5,
            "acousticness": 0.9,
            "speechiness": 0.0,
            "instrumentalness": 0.6,
            "liveness": 0.05,
            "popularity": 45,
            "release_decade": 2020,
            "mood_intensity": 0.5,
            "key": "minor",
            "complexity": 0.25,
        },
    ]
    user_prefs = {
        "genre": "pop",
        "mood": "happy",
        "target_energy": 0.8,
        "target_valence": 0.85,
        "target_acousticness": 0.2,
        "target_popularity": 80,
        "target_decade": 2020,
        "target_mood_intensity": 0.8,
        "target_key": "major",
        "target_complexity": 0.4,
    }

    results = recommend_songs(user_prefs, songs, k=2)

    assert len(results) == 2
    assert "reliability" in results[0][2]


def test_reliability_report_warns_for_missing_genre():
    songs = [
        {
            "id": 1,
            "title": "Calm Track",
            "artist": "Artist",
            "genre": "ambient",
            "mood": "chill",
            "energy": 0.3,
            "tempo_bpm": 70,
            "valence": 0.5,
            "danceability": 0.3,
            "acousticness": 0.9,
            "speechiness": 0.0,
            "instrumentalness": 0.9,
            "liveness": 0.1,
            "popularity": 35,
            "release_decade": 2020,
            "mood_intensity": 0.4,
            "key": "minor",
            "complexity": 0.3,
        }
    ]

    report = build_reliability_report(
        {
            "genre": "bluegrass",
            "mood": "chill",
            "target_energy": 0.3,
            "target_valence": 0.5,
            "target_acousticness": 0.9,
            "target_popularity": 35,
            "target_decade": 2020,
            "target_mood_intensity": 0.4,
            "target_key": "minor",
            "target_complexity": 0.3,
        },
        songs,
        k=1,
    )

    assert report.variant_count > 0
    assert any("not in the catalog" in warning for warning in report.warnings)


def test_recommend_songs_rejects_non_positive_k():
    with pytest.raises(RecommendationError):
        recommend_songs({"genre": "pop", "mood": "happy", "target_energy": 0.8}, [], k=0)
