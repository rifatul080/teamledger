# Scoring methodology

Author credits on a research paper should reflect three things:

1. **Effort** — how much work went into the contribution.
2. **Quality** — how good the work was, judged by a reviewer who is not
   the contributor.
3. **Timeliness** — whether the contribution landed on schedule.

TeamLedger's scoring module computes a per-task point total and rolls it up
to a project dashboard. The math lives entirely in
`backend/app/scoring/engine.py` — a **pure** module that depends only on
the standard library and `Decimal`. There is no DB, no IO, no clock, no
randomness in the formula itself. This page describes the formula and a
worked example.

## Formula

For each completed task:

```
points = weight × (quality / 5) × timeliness × category_multiplier + adjustment
```

| Field                 | Range / type                                | Source                                                |
|-----------------------|---------------------------------------------|-------------------------------------------------------|
| `weight`              | integer 1..10                               | Leader-set on task create                              |
| `quality`             | integer 1..5                                | Reviewer's rating at accept-time                       |
| `timeliness`          | `Decimal` in (0, 1]                         | Derived from due vs done-at, per project bands         |
| `category_multiplier` | `Decimal` in [0, 5]                         | Project-level CRediT multiplier                        |
| `adjustment`          | signed `Decimal` (any magnitude)            | Manual ± with reason; counted separately for audit     |

### Timeliness bands

Default (per project, leader-editable via `PUT /projects/{id}/timeliness`):

| Lateness (days past due) | Multiplier |
|--------------------------|------------|
| 0                        | 1.00       |
| 1–2                      | 0.90       |
| 3–6                      | 0.75       |
| ≥ 7                      | 0.50       |

Bands are monotone non-increasing; the API rejects out-of-order values
(`422 req.invalid`).

### CRediT categories

The 14 [CRediT contributor roles](https://credit.niso.org/) ship as
seed data (`alembic/versions/0002_seed_credit.py`). Each project may
override the multiplier per category:

```json
[
  {"category_code": "software", "multiplier": "1.25"},
  {"category_code": "writing_original_draft", "multiplier": "1.10"}
]
```

The default multiplier is 1.0 for any unlisted category.

### Adjustments

A leader can add `±n` points with a written reason (`reason` 1..2000
characters). Adjustments are stored separately and rendered as a separate
line in the dashboard and the CSV / PDF export. Each adjustment writes
an `AuditEvent` of type `score.adjustment_add`.

## Why these choices

* **`Decimal`** — the formula mixes ints (weight, quality) and decimals
  (timeliness, multiplier). `Decimal` is the only sane way to avoid the
  cumulative drift of binary floats. No `float` ever appears in
  `app/scoring/`.
* **Quality caps at 5** — keeps the visual scale familiar (1..5 stars).
* **Timeliness is bounded** in (0, 1] — a late task can lose up to half
  its points but never go negative.
* **Adjustment is additive, not multiplicative** — a leader's override is
  auditable separately. Mixing it into the multiplier would make leader
  discretion invisible.

## Worked example

Two participants, one project, three tasks.

### Inputs

| Task | Assignee | Category              | Weight | Quality | Due    | Done    |
|------|----------|-----------------------|--------|---------|--------|---------|
| T1   | Alice    | `software`            | 5      | 4       | Jan 10 | Jan 8   |
| T2   | Bob      | `software`            | 7      | 3       | Jan 12 | Jan 18  |
| T3   | Alice    | `writing_original_draft` | 3    | 5       | Feb 1  | Feb 1   |

Project multipliers: `software = 1.25`, others = 1.0.

Timeliness bands: 0 days → 1.0; 1–2 → 0.9; 3–6 → 0.75; ≥7 → 0.5.

### Per-task points

```
T1 (Alice, software, w=5, q=4, on time):
    points = 5 × (4/5) × 1.00 × 1.25 = 5 × 0.8 × 1.0 × 1.25 = 5.0

T2 (Bob,   software, w=7, q=3, 6 days late):
    points = 7 × (3/5) × 0.75 × 1.25 = 7 × 0.6 × 0.75 × 1.25 = 3.9375

T3 (Alice, writing,  w=3, q=5, on time):
    points = 3 × (5/5) × 1.00 × 1.00 = 3 × 1.0 × 1.0 × 1.0  = 3.0
```

(Decimals are stored verbatim — the dashboard rounds to 2 d.p. on display.)

### Roll-up

| Participant | Tasks                  | Total |
|-------------|------------------------|-------|
| Alice       | T1 (5.0) + T3 (3.0)    | 8.0   |
| Bob         | T2 (3.9375)            | 3.9375 |

Suggested author order: **Alice, Bob**.

## Author order finalisation

1. Leader calls `GET /projects/{id}/score` to inspect the suggestion.
2. Leader may pin specific participants to positions (a separate
   `author_order_pin` table — not yet exposed in v1.0.0; see
   `docs/known-limitations.md`).
3. Leader calls `POST /projects/{id}/author-order/finalize` with the
   final positions. The response contains a `snapshot_id`.
4. The snapshot row is **immutable**; the order, scores, settings, and
   inputs are SHA-256'd. Subsequent re-finalisations write new snapshots.
5. `/export.pdf`, `/export.csv`, `/statement.txt` always read from a
   chosen `snapshot_id`.

## Reproducibility

* The scoring engine is pure: given the same inputs it produces the same
  output. Tests in `tests/unit/test_scoring_engine.py` cover **38
  hand-computed cases** (including the example above, plus edge cases
  on every category multiplier and band).
* Property tests (`tests/property/test_scoring_props.py`) use Hypothesis
  to confirm the following invariants hold for any random input:
  - `total_points == sum(by_category.values())`
  - `sum(participants[i].share_pct) ≈ 100.0`
  - `category_multiplier = 0` zeroes the task's contribution
  - `timeliness = 0.0` produces `0` task points (the engine clamps the
    band floor at `late_severe`).
  - Adjustments are additive and bounded only by the input.

## Audit and trust

Every score-affecting event — `score.adjustment_add`, `author.order_finalize` —
is recorded in `AuditEvent`. The audit log is leader-only, append-only, and
exported alongside the snapshot PDF.

## Future work (post-v1.0.0)

* Pinned positions (already partly designed; see v1.x roadmap).
* Time-based weighting ("weighted by wall-clock hours" instead of estimate).
* Bayesian shrinkage for participants with very few tasks.

These are listed under `docs/known-limitations.md` so readers do not
expect them in v1.0.0.
