# Bookworm v3 — Project Plan

Decisions reached before the first commit. Versions were confirmed live against
PyPI / npm / endoflife.date on 2026-07-31; re-verify before treating them as
current.

## 1. Decisions locked in

| Area | Choice |
|---|---|
| Repo | Monorepo at `~/bookworm-v3`, `/backend` + `/frontend` |
| Backend | FastAPI + SQLAlchemy 2.0 + Alembic |
| Frontend | Vite + React 19 + TanStack Query + Tailwind (SPA) |
| Auth | Own it — email/password, Argon2, JWT in httpOnly cookie |
| Book data | **Hardcover** as sole primary source, behind a pluggable provider |
| Persistence | Cache-on-save — a `books` row is written only when someone shelves it |
| Shelves | Custom named shelves **and** orthogonal reading status |
| DB | Postgres 18 via docker-compose |
| First commit | Bare scaffold, no features |

## 2. Versions

**Runtimes**

- Python **3.14.6** — current stable, EOL 2030. Installed via `uv`, pinned in
  `.python-version`. The system `python3` (3.9.3) is untouched.
- Node **24.18.1** — the Active LTS. Node 26.5.1 exists but does not become LTS
  until 2026-10-28. Pinned in `.node-version` via fnm.
- Postgres **18.4**

**Backend** — fastapi 0.141.1 · sqlalchemy 2.0.51 · alembic 1.18.5 ·
pydantic 2.13.4 · uvicorn 0.52.0 · httpx 0.28.1 · pytest 9.1.1 · ruff 0.16.1 ·
psycopg 3 · argon2-cffi

**Frontend** — react 19.2.8 · vite 8.2.0 · @tanstack/react-query 5.101.4 ·
tailwindcss 4.3.3 · react-router 8.3.0 · typescript 5.9 (chosen over 7.x to
avoid ESLint/Vite plugin friction)

## 3. Data model

Shelves and reading status are orthogonal, which gives two concepts rather than
one:

```
users ──┬── shelves ──── shelf_items ──── books ──── book_authors ──── authors
        │                                   │
        └── user_books ─────────────────────┴── book_ratings
            (status, rating, review)            (one row per source)
```

- **`books`** — identity keys (`hardcover_id`, `isbn13`, `isbn10`,
  `google_books_id`, `open_library_id`, `goodreads_id`) plus title, description,
  page_count, cover_url, published_date, `metadata_refreshed_at`.
- **`authors` / `book_authors`** — normalized rather than a JSON blob, so "show
  me everything on my shelves by Le Guin" is a join, not a scan.
- **`book_ratings`** — PK `(book_id, source)`, source ∈
  `hardcover | google | open_library | goodreads | storygraph`. Multiple sources
  coexist; the UI picks what to show. This is what keeps the ratings question
  reversible.
- **`user_books`** — PK `(user_id, book_id)`; carries `status`
  (want_to_read/reading/read/dnf), the user's own rating, review, started and
  finished dates.
- **`shelves`** — user-created, `unique(user_id, slug)`.

Key property: a book can sit on three shelves and still have exactly one reading
status. That is Goodreads' actual model.

## 4. Why Hardcover

Evaluated against real requests, not documentation.

| Source | Verdict |
|---|---|
| **Hardcover** | **Chosen.** Official free GraphQL API at `api.hardcover.app/v1/graphql`. Search returns the full detail payload in one call: `rating`, `ratings_count`, `ratings_distribution`, `description`, `pages`, `cached_tags`, `image`, `contributions`, `editions`, `release_date`. |
| Google Books | Keyless access now returns `quota_limit_value: "0"` — disabled, not merely throttled. Requires a key before search works at all. No usable rating depth (Google Play Books has scores but vanishingly few reviews). |
| Open Library | Confirmed sparse. Real samples: The Fifth Season 19 ratings, Henry V 14; best case across the sample was 1,399. |
| StoryGraph | `app.thestorygraph.com` returns HTTP 403 behind a Cloudflare challenge. The unofficial `storygraph-api` depends on Selenium to pass it — slower than the Goodreads scraper, not faster; last release March 2025; synchronous `requests` would block the event loop; no documented title→UUID search. Routing around the challenge is circumventing an access control. |
| Goodreads via Apify | Richest data, but slow, paid, and legally grey. |

Rating depth on a 20-book sample: median **911**, max **7,739** — roughly
50–100× Open Library on the same titles. Ceiling: Hardcover's most-read book has
~10,049 ratings.

Providers will sit behind an interface introduced alongside the first
implementation, so Google Books or an Apify Goodreads scraper can drop in later
without touching the API or UI layers. `app/providers/` is an empty package
until then — the abstraction gets written when there are two things to abstract
over, not before.

## 5. Known constraints

- **Rate limit: 60 req/min**, 30s query timeout. Too low for multi-user. Search
  responses need a server-side TTL cache — start in-process or in Postgres, add
  Redis only if measurement demands it.
- **Search ranking is not usable raw.** See [phase-4-search-ranking.md](phase-4-search-ranking.md).
- **Docker Desktop is v20.10.6 (April 2021)** — five years stale on macOS Tahoe.
  An upgrade was started but needs verification before compose is usable.

## 6. Deployment (open)

Verified against vendor pages on 2026-07-31.

| | Render | Railway | Fly.io |
|---|---|---|---|
| Free tier | Real, but the web service spins down after 15 min idle (~1 min cold start); free Postgres expires 30 days after creation, 1 GB, no backups | None. $5 trial credit over 30 days; free plan is $1/mo credit | None meaningful |
| Realistic cost | ~$13/mo — $7 Starter service + $6 Postgres, static site free | ~$10–20/mo — Hobby $5/mo incl. $5 usage | Usage-based |

Not yet decided.

## 7. Secrets

The Hardcover token lives in `.env` (gitignored, mode 600) and never in a
commit. It was pasted into a chat transcript during evaluation, so **rotate it**
at hardcover.app → account settings → API before this goes anywhere real.
