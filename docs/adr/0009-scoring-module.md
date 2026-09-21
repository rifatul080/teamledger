# ADR-0009 — Pure scoring module with Decimal arithmetic

- **Status:** accepted
- **Context:** Spec says scoring belongs to a project; numbers must trace back to inputs; same inputs must produce the same outputs.
- **Decision:** `backend/app/scoring/engine.py` is a pure module:
  - Inputs: `ScoreProjectInputs` dataclass with project settings, participants, tasks, adjustments.
  - Output: `ScoreResult` dataclass with per-participant totals, by-category breakdown, suggested order, computed points per task.
  - No imports of `db`, `datetime.now()`, `requests`, `smtplib`, etc.
  - Uses `decimal.Decimal` throughout; `getcontext().prec = 28`.
  - One explicit rounding step at the end (`ROUND_HALF_UP`, 6 places).
  - Tie-break: `(points desc, display_name_ci asc, user_id asc)`.
- **Consequences:**
  - Property tests are trivial: pass the same inputs twice → same bytes.
  - Re-running old snapshots is possible (regression test for score engine changes).
  - Reusing the module for exports is direct.
- **Alternatives considered:**
  - Service-class with DI — works, but pure functions give better test ergonomics for property testing.
