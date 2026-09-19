# Workout Agent

A LangChain-ready MCP server and CLI. **Notion is the source of truth** for workouts. ExerciseDB supplies demonstration videos. There is no hosted workout database and no per-user scope — one Notion workspace is the whole dataset.

## What lives where

| Thing | Where you add / edit it |
|---|---|
| Lifts, actual weights, completed | Notion **Workout Lifts** |
| Cardio, protein, steps | Notion **Daily Logs** |
| Weekly page you open and work from | Notion **Weekly Workouts** |
| Long-term goals | Notion **Goals** |
| Gyms / home setups | Notion **Workout Locations** |
| Height, weight, main lifts | Notion **Body Stats** |
| Demo videos / GIFs | ExerciseDB |
| Agent tools | MCP at `/mcp` or `workout` CLI |

When you type `195` into **Actual weight**, that *is* the number the agent uses next week. Goals, locations, and the latest body-stats row are read the same way.

## Notion UI

Create one page called **Workout Agent** and drop these six **full-page databases** on it (or linked views of them). That page is the UI: click **New** to add a row, edit cells to update. Share every database with your [internal integration](https://www.notion.so/my-integrations).

### Goals (`NOTION_GOALS_DATABASE_ID`)

Add a row when you pick a target. Mark Status `Done` when you hit it.

| Property | Type | Who fills it |
|---|---|---|
| Name | Title | You (`Bench 225`) |
| Description | Text | You |
| Target | Text | You (`225 lb`) |
| Metric | Text | You (`bench`, `weight`, `protein`) |
| Deadline | Date | You |
| Status | Select: `Active`, `Paused`, `Done` | You |

### Workout Locations (`NOTION_LOCATIONS_DATABASE_ID`)

One row per place you train. Check **Default** on the usual one so the agent plans around its equipment.

| Property | Type | Who fills it |
|---|---|---|
| Name | Title | You (`Home gym`, `Equinox`) |
| Description | Text | You |
| Equipment | Text | You (`barbell, rack, dumbbells`) |
| Default | Checkbox | You |

### Body Stats (`NOTION_STATS_DATABASE_ID`)

New row per check-in. The newest **Date** is what the agent uses.

| Property | Type | Who fills it |
|---|---|---|
| Name | Title | You or the date |
| Date | Date | You |
| Height | Text | You |
| Weight | Text | You |
| Squat | Text | You |
| Bench | Text | You |
| Deadlift | Text | You |
| Overhead press | Text | You |

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
# set MCP_AGENT_TOKEN, NOTION_TOKEN, and the database ids
pip install -e ".[dev]"
uvicorn app.main:app --reload
# or
docker compose up --build
```

MCP: `http://localhost:8000/mcp` with `Authorization: Bearer <MCP_AGENT_TOKEN>`.

```bash
workout notion context
workout notion goals
workout notion locations
workout notion stats
workout notion lifts
workout notion recent
workout notion publish-week --week-start 2026-09-21 --dry-run
```

## Agent week loop

1. `get_planning_context` — active goals, default location, latest body stats
2. `get_recent_lift_performance` — last **Actual weight**
3. `create_lifting_workout` — next week’s lifts into Workout Lifts
4. `publish_weekly_workout_to_notion` — week page + demos + goals/stats/location
5. You train, fill **Actual weight**, and update Goals / Body Stats in Notion
6. Repeat

Writable MCP tools: lifting workouts, cardio, protein, steps, goals, workout locations, body stats. Exercise search is read-only.

## Tests

```bash
pytest
```
