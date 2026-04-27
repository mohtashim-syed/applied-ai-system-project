# Reliability-Aware Music Recommender

## Title and Summary

This project is a content-based AI music recommender that matches a listener profile to songs in a small catalog and explains why each recommendation was chosen. Its most important upgrade is a built-in reliability layer: before finalizing results, the system perturbs the user profile slightly, reruns the ranking, and measures whether the same songs remain near the top. That matters because an AI system should not only produce answers, it should also help users understand when those answers are stable and when they should be treated cautiously.

## Original Project From Modules 1-3

My original Modules 1-3 project was **Music Recommender Simulation**. Its goal was to model how a transparent recommendation system could use structured song features such as genre, mood, energy, valence, and acousticness to rank songs for a listener profile. The original version could load a CSV catalog, score songs with a hand-built heuristic, and return readable explanations for why a track was recommended, but it did not yet test how dependable those recommendations were under slightly changed inputs.

## Why This Version Is Stronger

This repo evolves the original project into a more employer-ready AI system by adding:

- integrated reliability testing inside the recommendation pipeline
- guardrails for invalid or unsupported profiles
- logging for catalog loading and recommendation runs
- reproducible CLI behavior with documented setup and tests
- clearer separation between data loading, scoring, reliability auditing, and presentation

## Stretch Features

This version also includes two optional enhancement features:

- `Test Harness / Evaluation Script`: `scripts/evaluate_system.py` runs predefined profiles, checks expected outcomes, and prints a pass/fail summary with stability metrics.
- `Agentic Workflow Enhancement`: `python3 src/main.py --trace <profile_name>` exposes the system's intermediate decision chain, including normalized preferences, variant counts, candidate scores, and the reasons that shaped the ranking.

## Architecture Overview

System diagram source: [assets/system-diagram.mmd](/Users/mohtashim/Desktop/repo/applied-ai-system-project/assets/system-diagram.mmd)

The system has five main components:

- `src/main.py` is the command-line entry point. It selects a built-in profile, loads the catalog, runs the recommender, and prints the final report.
- `load_songs()` reads `data/songs.csv` and converts each row into typed song attributes.
- `recommend_songs()` is the main AI recommendation component. It scores every song against the active profile and produces explanations.
- `build_reliability_report()` acts as an integrated evaluator/tester. It creates nearby profile variants, reruns scoring, and measures how stable the top recommendations are.
- The human reviewer is part of the loop through profile selection, reading the reliability summary, and checking warnings or edge cases.

Data flow is:

`Human input -> CLI app -> song catalog + profile validation -> song scoring -> reliability audit -> ranked recommendations + warnings + stability summary`

Human and testing involvement appear in two places:

- During runtime, the user can inspect stability warnings and decide whether to trust brittle recommendations.
- During development, `pytest` verifies the ranking, explanations, guardrails, and reliability behavior.

## Setup Instructions

1. Clone the repository:

```bash
git clone https://github.com/mohtashim-syed/applied-ai-system-project.git
cd applied-ai-system-project
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the default profile:

```bash
python3 src/main.py
```

5. List available profiles:

```bash
python3 src/main.py --list
```

6. Run a specific profile:

```bash
python3 src/main.py chill_lofi
```

7. Run tests:

```bash
python3 -m pytest
```

8. Run the evaluation harness:

```bash
python3 scripts/evaluate_system.py
```

9. View the observable decision chain for one profile:

```bash
python3 src/main.py --trace ghost_genre
```

## Sample Interactions

These examples were generated from the current codebase.

### Example 1: High-energy pop listener

Input:

```bash
python3 src/main.py high_energy_pop
```

Output excerpt:

```text
#1  Sunrise City  —  Neon Echo
Score : 12.06 / 12.5 pts
Why   :
  +3.0 mood matches 'happy'
  +3.68 energy similarity (song 0.82, target 0.90)
  +1.0 genre matches 'pop'
  ...
  reliability stable (13/13 nearby profile checks)

Reliability Audit
Nearby profile checks run : 13
Stable top-5 ratio        : 100%
Average recommendation stability : 95%
```

What this shows:

- the recommender can identify a very strong pop match
- the explanation is feature-by-feature rather than opaque
- the reliability audit confirms the top results are consistent

### Example 2: Chill lo-fi listener

Input:

```bash
python3 src/main.py chill_lofi
```

Output excerpt:

```text
#1  Midnight Coding  —  LoRoom
Score : 12.17 / 12.5 pts
Why   :
  +3.0 mood matches 'chill'
  +3.84 energy similarity (song 0.42, target 0.38)
  +1.0 genre matches 'lofi'
  ...
  reliability stable (13/13 nearby profile checks)

#5  Coffee Shop Stories  —  Slow Stereo
...
  reliability watch closely (9/13 nearby profile checks)
```

What this shows:

- the system can separate highly aligned lo-fi tracks from weaker fallback matches
- reliability is not binary; some suggestions are clearly more stable than others

### Example 3: Unsupported genre with guardrails

Input:

```bash
python3 src/main.py ghost_genre
```

Output excerpt:

```text
#1  Library Rain  —  Paper Lanterns
Score : 11.34 / 12.5 pts
Why   :
  +3.0 mood matches 'chill'
  +4.00 energy similarity (song 0.35, target 0.35)
  ...
  reliability stable (13/13 nearby profile checks)
  guardrail: Requested genre 'bluegrass' is not in the catalog, so results will rely on mood and numeric similarity.

Reliability Audit
Guardrails:
  - Requested genre 'bluegrass' is not in the catalog, so results will rely on mood and numeric similarity.
```

What this shows:

- the app handles unsupported inputs safely instead of failing silently
- it still produces useful recommendations by falling back to available signals
- the guardrail message makes the limitation explicit to the user

## Design Decisions

To be completed later.

Use this section to explain:

- why the system uses a content-based recommender
- why the reliability audit is integrated into the main pipeline
- what trade-offs were made around simplicity, interpretability, and scale

## Testing Summary

The project includes four reliability checks: automated tests, runtime logging, confidence-style stability scoring, and a dedicated evaluation harness. `python3 -m pytest` currently passes 6 out of 6 tests, covering recommendation ranking, explanation generation, guardrail handling, the integrated reliability report, and the new observable trace path.

The app also logs catalog loading and recommendation runs so failures are easier to diagnose. In manual evaluation, the `ghost_genre` edge-case profile still produced usable results, and its reliability audit reported 13 nearby-profile checks with 100% stable top-5 recommendations and 95% average stability, while also warning that the requested genre was missing from the catalog.

For broader verification, `python3 scripts/evaluate_system.py` runs multiple named scenarios and checks expected winners, warning behavior, and minimum stability thresholds. The main weakness is still limited catalog coverage rather than broken scoring logic. When context is sparse or unsupported, the system falls back to mood and numeric similarity, so the recommendations still work, but the guardrails make that lower-confidence situation explicit.

## Reflection

This system has clear limitations and biases. It relies on a small hand-curated catalog, so some genres and moods are underrepresented or missing entirely, which can bias recommendations toward the limited styles already present in the data. It also uses rule-based scoring with exact matches for some labels, so it can be too rigid when a user’s intent is nuanced or when two moods are similar but not identical.

The AI could be misused if someone treated its recommendations as objective truth instead of a lightweight prototype. A user could also overtrust recommendations even when the profile is unsupported by the catalog. To reduce that risk, I added guardrail warnings, explanation traces, and a reliability audit so the system makes its uncertainty visible instead of pretending to be universally accurate.

What surprised me most during reliability testing was that some edge-case profiles were more stable than I expected. For example, even when the requested genre did not exist in the catalog, the system still produced highly stable recommendations because the numeric features and mood signal were strong enough to anchor the ranking. At the same time, that stability did not mean the recommendations were perfect, which reinforced the difference between consistency and correctness.

My collaboration with AI during this project was useful but not automatic. One genuinely helpful suggestion was integrating the evaluator directly into the main recommendation pipeline instead of treating testing as a separate script, because that made reliability affect the actual output users see. One flawed suggestion was earlier README and diagram language that described outdated scoring weights and older flow details after the code had evolved. I had to manually verify the implementation, correct the documentation, and make sure the final explanation matched the real system rather than an earlier draft.

This project says that I approach AI engineering as both a builder and a reviewer. I care about making systems useful, but I also care about whether they are explainable, testable, and honest about uncertainty. Instead of stopping at a demo that looked correct, I pushed the project toward reliability checks, guardrails, and measurable evaluation, which reflects the kind of engineer I want to be: practical, responsible, and deliberate about how AI behaves in real use.

## Repository Structure

```text
applied-ai-system-project/
├── assets/
│   ├── .gitkeep
│   └── system-diagram.mmd
├── data/
│   └── songs.csv
├── scripts/
│   └── evaluate_system.py
├── src/
│   ├── main.py
│   ├── profiles.py
│   └── recommender.py
├── tests/
│   └── test_recommender.py
├── model_card.md
├── reflection.md
├── requirements.txt
└── README.md
```
