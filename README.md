# Bookworm

Search books, see real ratings, and shelve them on a bookshelf that looks like a bookshelf.

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.14 · FastAPI · SQLAlchemy 2.0 · Alembic |
| Frontend | Node 24 LTS · React 19 · TypeScript 5.9 · Vite · TanStack Query · Tailwind 4 |
| Database | Postgres 18 |
| Book data | [Hardcover](https://hardcover.app) GraphQL API |

Why these, and why Hardcover over Goodreads/StoryGraph/Open Library:
[docs/plan.md](docs/plan.md).

## Prerequisites

```sh
brew install fnm uv
fnm install            # reads .node-version
uv python install 3.14
```

Postgres runs in Docker. Docker Desktop must be installed and running.

## Getting started

```sh
cp .env.example .env       # then add your HARDCOVER_TOKEN
make setup                 # uv sync + npm install
make db-up                 # Postgres 18 on :5432
make backend               # API on :8000, docs at /docs
make frontend              # UI on :5173
```

`make help` lists every target.

## Layout

```
backend/
  app/
    api/v1/       route modules, assembled in router.py
    db/           engine, session, declarative Base
    models/       SQLAlchemy models
    schemas/      Pydantic request/response types
    services/     business logic
    providers/    book data sources
  alembic/        migrations
  tests/
frontend/
  src/
    lib/          api client, query client
docs/             design decisions
```

Everything under `models/`, `schemas/`, `services/`, and `providers/` is an empty
package today — the directories exist so the first real module has an obvious
home.

## Documentation

- [docs/plan.md](docs/plan.md) — decisions, versions, data model, provider
  evaluation, deployment options
- [docs/phase-4-search-ranking.md](docs/phase-4-search-ranking.md) — the search
  re-ranking problem and its validated prototype

## Roadmap

| Phase | | |
|---|---|---|
| 1 | Scaffold | ✅ |
| 2 | Schema + migrations | |
| 3 | Auth (email/password, JWT in httpOnly cookie) | |
| 4 | Book search end-to-end | |
| 5 | Book detail + ratings | |
| 6 | Shelves CRUD + reading status | |
| 7 | Visual bookshelf UI | |
| 8 | Deploy | |
