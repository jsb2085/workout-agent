# Workout Agent

FastAPI backend for a SwiftUI workout app. Each person (you and your wife) creates an email/password account and only sees their own data. A LangChain deep agent can later connect over MCP to read everything and write protein, steps, lifting workouts, and cardio.

## Stack

- FastAPI + SQLAlchemy 2 (async) + Alembic
- Postgres 16
- MinIO (S3-compatible) for physique photos
- Email/password login → JWT
- FastMCP mounted at `/mcp`
- ExerciseDB for workout demonstration videos (MP4 via RapidAPI V2, GIF via the free hosted API)

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

## Exercise videos (ExerciseDB)

The agent and the SwiftUI app can look up demonstration media from [ExerciseDB](https://docs.ascendapi.com/products/edb-v2/overview).

| Env | Purpose |
|---|---|
| `EXERCISEDB_API_KEY` | RapidAPI key. When set, requests go to ExerciseDB V2 and each exercise includes an MP4 `video_url`. |
| `EXERCISEDB_API_HOST` | RapidAPI host (default: `edb-with-videos-and-images-by-ascendapi.p.rapidapi.com`) |
| `EXERCISEDB_BASE_URL` | Optional full base URL override |
| *(no key)* | Uses the free hosted API at `https://oss.exercisedb.dev`. `demo_url` is an animated GIF. |

Subscribe on RapidAPI: [EDB with Videos and Images](https://rapidapi.com/ascendapi/api/edb-with-videos-and-images-by-ascendapi).

Authenticated REST:

| Method | Path | What it returns |
|---|---|---|
| `GET` | `/exercises?name=bench%20press` | Search results with `demo_url` / `video_url` / `gif_url` |
| `GET` | `/exercises/{exercise_id}` | One exercise, including demonstration media |
| `GET` | `/exercises/for-workouts` | Current user's lifting workouts with matched videos |
| `GET` | `/lifting-workouts/{id}/exercise-video` | Video for one saved lift |

Each exercise payload includes `demo_url` (play this), `media_kind` (`video` or `gif`), plus muscles, equipment, and instructions.

## Weekly plan → Notion

The agent writes the week it just planned into a Notion database you can check off and work from. Postgres stays the source of truth; Notion is the working copy.

### Design the template once

1. Create a Notion [internal integration](https://www.notion.so/my-integrations) and copy the token into `NOTION_TOKEN`.
2. Create a full-page database named **Weekly Workouts**.
3. Add these properties (Name already exists as the title):

| Property | Type | Why |
|---|---|---|
| Name | Title | Page title, e.g. `Jacob — Week of Sep 21–27` |
| Week | Date (with end date) | The planned week |
| Status | Select: `Planned`, `In progress`, `Done` | So you can run the week |
| Focus | Text | e.g. hypertrophy / bench |
| Athlete | Text | You or your wife |

4. Create a second database named **Workout Lifts** (this is how weights come back to the agent):

| Property | Type | Who fills it |
|---|---|---|
| Name | Title | Agent (lift name) |
| Date | Date | Agent |
| Goal weight | Text | Agent |
| **Actual weight** | Text | **You, after the set** |
| Reps | Number | Agent |
| Completed | Checkbox | You or the agent |
| Workout id | Text | Agent (do not edit) |
| Athlete | Text | Agent |
| Week start | Date | Agent |

5. Optional: add a Weekly Workouts template called **Weekly workout**, then put its page id in `NOTION_TEMPLATE_ID`.
6. Share **both** databases with the integration. Put the ids in `NOTION_DATABASE_ID` and `NOTION_LIFTS_DATABASE_ID`.

Suggested Notion views: a calendar on `Week`, and a board grouped by `Status`.

The page body the agent fills is the working template:

- Week title + focus callout
- One heading per day (Mon–Sun)
- A checkbox per lift (`5 reps @ 185`) and per cardio
- ExerciseDB demo (MP4 or GIF) under each lift
- Protein / steps goals
- Rest days stay on the page so the week is complete

### Publish

After the agent creates the week's lifting/cardio/protein/steps rows:

```bash
workout notion publish-week --email you@example.com --week-start 2026-09-21 --focus "bench + squat"
workout notion publish-week --email you@example.com --dry-run
```

Or MCP `publish_weekly_workout_to_notion` with the same fields (`dry_run=true` to preview). Pass `plan_json` if the agent authored a `WeeklyPlan` instead of reading saved rows.

### Sync weights back before next week

Enter the weight you actually hit in **Workout Lifts → Actual weight** (not by editing the weekly page text). Then:

```bash
workout notion sync --email you@example.com --week-start 2026-09-21
workout notion recent --email you@example.com
```

The agent loop is:

1. `sync_notion_workouts_to_agent` — copies Actual weight / completed into `lifting_workouts`
2. `get_recent_lift_performance` — latest actual per lift
3. Plan next week from those numbers (`create_lifting_workout` with a new `goal_weight`)
4. `publish_weekly_workout_to_notion` — new week page + new lift rows

Matching uses `Workout id` first, then lift name + date. Re-publishing the same week updates goal/date/reps but does **not** overwrite a weight you already logged.

## MCP server

Same process as the API, streamable HTTP at `/mcp`.

Protect it with:

```http
Authorization: Bearer <MCP_AGENT_TOKEN>
```

Every tool takes `email` and/or `user_id` so one agent can act for either of you.

**Read tools:** `resolve_user`, plus `list_*` / `get_*` for lifting workouts, cardio, gym locations, performance goals, physique photos, protein, steps, and body stats. Physique photos also expose `get_physic_photo_url` and `get_physique_comparison_photos` (latest vs goal, with download URLs). ExerciseDB tools: `search_exercise_videos`, `get_exercise_video`, and `get_workout_exercise_videos` (matches each saved lift to a demo MP4 or GIF). After planning a week, `publish_weekly_workout_to_notion` writes that week into the Notion template. Before the next week, `sync_notion_workouts_to_agent` pulls Actual weight back, and `get_recent_lift_performance` is what the planner should read.

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
