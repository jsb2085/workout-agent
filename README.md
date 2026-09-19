# Workout Agent

A LangChain-ready MCP server and CLI. **Notion is the source of truth** for workouts. ExerciseDB supplies demonstration videos. There is no hosted workout database, no physique-photo store, and no per-user scope — one Notion workspace is the whole dataset.

## What lives where

| Thing | Where |
|---|---|
| Lifts, actual weights, completed | Notion **Workout Lifts** |
| Cardio, protein, steps | Notion **Daily Logs** |
| Weekly page you open and work from | Notion **Weekly Workouts** |
| Demo videos / GIFs | ExerciseDB |
| Agent tools | MCP at `/mcp` or `workout` CLI |

When you type `195` into **Actual weight**, that *is* the number the agent uses next week. No sync job.

## Notion setup

Create an [internal integration](https://www.notion.so/my-integrations) and share these three databases with it.

### Workout Lifts (`NOTION_LIFTS_DATABASE_ID`)

| Property | Type | Who fills it |
|---|---|---|
| Name | Title | Agent (lift name) |
| Date | Date | Agent |
| Goal weight | Text | Agent |
| **Actual weight** | Text | **You, after the set** |
| Reps | Number | Agent |
| Completed | Checkbox | You |
| Week start | Date | Agent |

### Daily Logs (`NOTION_LOGS_DATABASE_ID`)

One row per day: Sprint / Run / Walk, Distance, Cardio reps, Cardio completed, Protein goal / actual, Steps goal / actual, Date.

### Weekly Workouts (`NOTION_DATABASE_ID`)

Name (title), Week (date range), Status (`Planned`, `In progress`, `Done`), Focus.

Optional: a database template + `NOTION_TEMPLATE_ID`.

## Run

```bash
cp .env.example .env
# set MCP_AGENT_TOKEN, NOTION_TOKEN, and the three database ids
pip install -e ".[dev]"
uvicorn app.main:app --reload
# or
docker compose up --build
```

MCP: `http://localhost:8000/mcp` with `Authorization: Bearer <MCP_AGENT_TOKEN>`.

```bash
workout notion lifts
workout notion recent
workout notion publish-week --week-start 2026-09-21 --dry-run
```

## Agent week loop

1. `get_recent_lift_performance` — read last **Actual weight** from Notion
2. `create_lifting_workout` — write next week’s lifts into Workout Lifts
3. `publish_weekly_workout_to_notion` — build the week page + ExerciseDB demos
4. You train and fill **Actual weight**
5. Repeat

Writable MCP tools: lifting workouts, cardio, protein, steps (all Notion). Exercise search is read-only.

## Tests

```bash
pytest
```
