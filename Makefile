.PHONY: install backend frontend dev dev-no-docker lint type test test-unit test-api test-ws test-property test-schemathesis test-load test-e2e test-scenario seed migrate clean trace coverage test-all verify

PY := python
PIP := $(PY) -m pip
NPM := npm

install:
	cd backend && $(PIP) install -e ".[api,test]"
	cd frontend && $(NPM) install

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && $(NPM) run dev

dev-no-docker:
	$(PY) backend/scripts/dev_bootstrap.py

migrate:
	cd backend && alembic upgrade head

seed:
	cd backend && $(PY) -m scripts.seed_demo

lint:
	cd backend && ruff check .
	cd frontend && $(NPM) run lint

type:
	cd backend && mypy app
	cd frontend && npx tsc --noEmit

test:
	cd backend && pytest -q

test-unit:
	cd backend && pytest -q tests/unit tests/services tests/property

test-api:
	cd backend && pytest -q tests/api

test-ws:
	cd backend && pytest -q tests/integration/test_ws_*.py

test-property:
	cd backend && pytest -q tests/property

test-schemathesis:
	cd backend && pytest -q -m schemathesis

test-load:
	cd backend && pytest -q -m load

test-e2e:
	cd frontend && $(NPM) run test:e2e

test-scenario:
	cd backend && pytest -q tests/scenario/test_twelve_week.py

coverage:
	cd backend && pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80 -q

# Runs EVERYTHING in the project as one command from a clean checkout.
# Order: install -> lint -> type -> unit -> api -> property -> coverage gate -> frontend lint/type/test.
# Skipped (with a print): schemathesis, load, e2e, scenario — these need live services and are opt-in.
test-all: install
	@echo "--- backend lint ---"; cd backend && ruff check .
	@echo "--- backend type ---"; cd backend && mypy app
	@echo "--- backend tests with coverage gate (80%) ---"; cd backend && pytest --cov=app --cov-fail-under=80 -q
	@echo "--- frontend lint ---"; cd frontend && npm run lint
	@echo "--- frontend type ---"; cd frontend && npx tsc --noEmit
	@echo "--- frontend tests ---"; cd frontend && npm test -- --run
	@echo "OK: all checks green"

verify: test-all

trace:
	cd backend && $(PY) scripts/traceability.py

security:
	cd backend && bandit -q -r app
	cd backend && pip-audit -r <($(PIP) freeze)
