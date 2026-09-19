# Workout Agent

Notion is the source of truth. **LangGraph plans the week. The CLI only moves data.**

```
workout pull  > context.json     # Notion → graph
# LangGraph reads context.json and writes plan.json
workout push --plan plan.json    # graph → Notion
```

## What the CLI does

| Command | Direction |
|---|---|
| `workout pull` | Read goals, locations, body stats, recent lifts/logs |
| `workout push --plan plan.json` | Write the graph’s week: lift rows, daily logs, week page + GIFs |

That is the whole CLI. You add and edit **Goals**, **Workout Locations**, and **Body Stats** in Notion. You log **Actual weight** on Workout Lifts after you train.

## LangGraph contract

`pull` writes a `PlanningContext`:

- `week_start` / `week_end`
- `recent_lifts` — latest Actual/Goal weight per lift
- `this_week_lifts` — rows already on the week (if any)
- `recent_logs` — last ~14 days of cardio/protein/steps
- `goals`, `locations`, `default_location`, `latest_body_stats`

`push` expects a `WeeklyPlan`: `title`, `week_start`, `week_end`, `focus`, `days[]` with `lifts` (`lift`, `reps`, `goal_weight`), optional `cardio` / `protein_goal` / `steps_goal`. Push creates lift rows, upserts that day’s log, and publishes the Weekly Workouts page (ExerciseDB GIF/MP4 under each lift).

MCP (same two jobs): `pull_planning_context`, `push_weekly_plan`. Optional ExerciseDB search tools if the graph wants them while planning.

## Notion UI

One **Workout Agent** page with six databases, each shared with your [integration](https://www.notion.so/my-integrations).

| Database | Env var | Who edits |
|---|---|---|
| Goals | `NOTION_GOALS_DATABASE_ID` | You (Name, Target, Deadline, Status) |
| Workout Locations | `NOTION_LOCATIONS_DATABASE_ID` | You (Name, Equipment, Default) |
| Body Stats | `NOTION_STATS_DATABASE_ID` | You (Date, Height, Weight, main lifts) |
| Workout Lifts | `NOTION_LIFTS_DATABASE_ID` | Graph writes the week; you fill **Actual weight** |
| Daily Logs | `NOTION_LOGS_DATABASE_ID` | Graph can write; you can edit |
| Weekly Workouts | `NOTION_DATABASE_ID` | Graph publishes the readable page |

## Run

```bash
cp .env.example .env
# NOTION_TOKEN + the six database ids
pip install -e ".[dev]"
workout pull --week-start 2026-09-21
workout push --plan plan.json --dry-run
```

MCP (if the graph uses tools instead of the CLI): `uvicorn app.main:app --reload` at `http://localhost:8000/mcp` with `Authorization: Bearer <MCP_AGENT_TOKEN>`.

## Tests

```bash
pytest
```
