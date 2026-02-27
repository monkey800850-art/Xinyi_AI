# Development Setup (WSL2 + MySQL)

## Prerequisites
- WSL2 Ubuntu environment
- MySQL server installed and running
- Python 3.10+ recommended

## Environment Files
- Copy `.env.example` to `.env` for shared defaults.
- Optionally create `.env.dev` and `.env.test` to override per environment.
- `APP_ENV` controls which file is loaded (`development`, `test`, `production`).

## Install Dependencies
- `python3 -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt`

## Run App (DB Connection Check)
- `python3 app.py`
- Startup will attempt DB connection and exit with a detailed error if it fails.

## Migrations (Alembic)
- Create a new migration:
  - `alembic revision -m "your message"`
- Apply migrations:
  - `alembic upgrade head`
- Roll back last migration:
  - `alembic downgrade -1`

## Checks
- Project can read `.env` (DB_* and APP_ENV values).
- Templates exist at `templates/standards/enterprise.csv` and `templates/standards/small_enterprise.csv`.
- `alembic upgrade head` creates `alembic_version` table and `system_bootstrap_test`.

