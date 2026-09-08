# Workout Agent

FastAPI backend for a SwiftUI workout app. Each person (you and your wife) creates an email/password account and only sees their own data. A LangChain deep agent can later connect over MCP to read everything and write protein, steps, lifting workouts, and cardio.

## Stack

- FastAPI + SQLAlchemy 2 (async) + Alembic
- Postgres 16
- MinIO (S3-compatible) for physique photos
- Email/password login → JWT
- FastMCP mounted at `/mcp`

## Quick start

```bash
cp .env.example .env
# set JWT_SECRET and MCP_AGENT_TOKEN
docker compose up --build
```

- API: http://localhost:8000
- OpenAPI docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001 (`minioadmin` / `minioadmin`)
- MCP: http://localhost:8000/mcp (Bearer `MCP_AGENT_TOKEN`)

Alembic runs `upgrade head` when the API container starts.

## Login

Create an account, then sign in with the same email and password. Passwords must be at least 8 characters.

```http
POST /auth/register
{"email": "you@example.com", "password": "at-least-8", "name": "Jordan"}

POST /auth/login
{"email": "you@example.com", "password": "at-least-8"}
```

Both return:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": { "id": "...", "email": "...", "name": "..." }
}
```

Send `Authorization: Bearer <jwt>` on every CRUD request. `GET /auth/me` returns the current user. Emails are unique and stored lowercase.

## REST resources

All rows are UUID-keyed and scoped to the JWT user.

| Resource | Prefix | Date filter |
|---|---|---|
| Lifting workouts | `/lifting-workouts` | `date_from`, `date_to` |
| Cardio | `/cardio` | `date_from`, `date_to` |
| Gym locations | `/gym-locations` | |
| Performance goals | `/performance-goals` | |
| Physique photos | `/physic-photos` | `date_from`, `date_to` |
| Protein | `/protein` | `date_from`, `date_to` |
| Steps | `/steps` | `date_from`, `date_to` |
| Body stats | `/body-stats` | `date_from`, `date_to` |

Each resource supports `GET /`, `GET /{id}`, `POST /`, `PATCH /{id}`, `DELETE /{id}`.

Body stats store `height`, `weight`, and current main lifts (`squat`, `bench`, `deadlift`, `overhead_press`). Lift fields are optional: omit them or send `null` for **I don't know**.

Photos are uploaded as multipart (`picture` file plus `is_goal`, `is_current`, `date`). Bytes go to the MinIO `physique-photos` bucket; Postgres stores `object_key`. `GET /physic-photos/{id}/url` returns a short-lived presigned GET URL. `GET /physic-photos/comparison` returns the latest progress photo and the goal photo with URLs (for the weekly-plan vision node).

## MCP server

Same process as the API, streamable HTTP at `/mcp`.

Protect it with:

```http
Authorization: Bearer <MCP_AGENT_TOKEN>
```

Every tool takes `email` and/or `user_id` so one agent can act for either of you.

**Read tools:** `resolve_user`, plus `list_*` / `get_*` for lifting workouts, cardio, gym locations, performance goals, physique photos, protein, steps, and body stats. Physique photos also expose `get_physic_photo_url` and `get_physique_comparison_photos` (latest vs goal, with download URLs).

**Write tools (create / update / delete only):** lifting workouts, cardio, protein, steps.

The agent cannot create, update, or delete gym locations, performance goals, photos, or body stats.

## Local tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Tests use SQLite and mock MinIO.

## Environment

See [.env.example](.env.example). Compose overrides `DATABASE_URL` and `MINIO_ENDPOINT` so the API talks to the `db` and `minio` services.
