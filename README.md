# Workout Agent

Notion is the source of truth. **LangGraph plans the week. The CLI moves data.**

## Notion UI (import from this repo)

Do not build the databases by hand. Import them from GitHub:

```bash
cp .env.example .env
# NOTION_TOKEN from https://www.notion.so/my-integrations
# Share any Notion page with that integration, then paste its URL:
workout setup --parent "https://www.notion.so/your-page-...." --write-env
```

That creates a **Workout Agent** page with a cover, how-to, section headers, and a colored caption above each of the six inline tables (Goals, Workout Locations, Body Stats, Workout Lifts, Daily Logs, Weekly Workouts). Example rows are seeded so you can edit immediately.

Prefer Notion's Import UI instead? Download the CSVs in [`notion/csv/`](notion/csv) and follow [`notion/README.md`](notion/README.md).

You add and edit **Goals**, **Workout Locations**, and **Body Stats** in Notion. After you train, log **Actual weight** on Workout Lifts — that is next week's input.

```
workout run --week-start 2026-09-21
```

That pulls Notion → runs the coach graph (`gpt-5.6-luna`) → pushes the week back.

You can still split the I/O if you want to inspect the JSON:

```
workout pull  > context.json
workout run --no-push --week-start 2026-09-21
workout push --plan plan.json
```

## Graph

Four nodes, OpenAI `gpt-5.6-luna` via `OPENAI_API_KEY`:

| Node | What it does |
|---|---|
| `assess_progress` | Compare active goals to recent **Actual weight**, logs, and body stats. What is moving, what is stalled, what this week should emphasize. |
| `plan_sessions` | Use that assessment plus the default workout location's equipment to pick the week's sessions (typically 3–5 lifting days, plus rest). |
| `assign_loads` | Set sets / reps / **Goal weight** from last Actual (else Goal, else body-stat lifts). Leaves Actual blank. |
| `assemble` | Deterministic. Fills all 7 days, keeps rest days empty, copies goals/location/stats onto the `WeeklyPlan`, never invents Actual weights. |

`assemble` is the extra node worth adding: the LLM nodes stay focused, and the published week is always a valid 7-day `WeeklyPlan`.

Skipped for now (no Notion fields yet): injury/recovery flags, per-day travel locations, a separate cardio/nutrition node. Those can slot in later without changing pull/push.

## CLI

| Command | Direction |
|---|---|
| `workout setup --parent PAGE` | Create the Notion page + databases from this repo |
| `workout run` | Pull → graph → push |
| `workout pull` | Read goals, locations, body stats, recent lifts/logs |
| `workout push --plan plan.json` | Write a finished `WeeklyPlan` |

Flags on `run` / `push`: `--dry-run`, `--no-videos`. `run` also has `--no-push` to print the plan only. `setup` has `--dry-run`, `--write-env`, `--in-place`, `--no-seed`.

## LangGraph contract

`pull` writes a `PlanningContext`:

- `week_start` / `week_end`
- `recent_lifts` — latest Actual/Goal weight per lift
- `this_week_lifts` — rows already on the week (if any)
- `recent_logs` — last ~14 days of cardio/protein/steps
- `goals`, `locations`, `default_location`, `latest_body_stats`

`push` expects a `WeeklyPlan`: `title`, `week_start`, `week_end`, `focus`, `days[]` with `lifts` (`lift`, `reps`, `goal_weight`), optional `cardio` / `protein_goal` / `steps_goal`. Push creates lift rows, upserts that day’s log, and publishes the Weekly Workouts page (ExerciseDB GIF/MP4 under each lift).

MCP: `setup_notion_workspace`, `run_weekly_planner`, `pull_planning_context`, `push_weekly_plan`. Optional ExerciseDB search tools if you want them mid-plan.

## Notion databases

Created by `workout setup` (or CSV import). Share the parent page with your [integration](https://www.notion.so/my-integrations).

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
# OPENAI_API_KEY, NOTION_TOKEN
# Share a Notion page with the integration, then:
workout setup --parent "https://www.notion.so/your-page-...." --write-env
pip install -e ".[dev]"
workout run --week-start 2026-09-21 --dry-run
workout run --week-start 2026-09-21
```

MCP (if a client uses tools instead of the CLI): `uvicorn app.main:app --reload` at `http://localhost:8000/mcp` with `Authorization: Bearer <MCP_AGENT_TOKEN>`.

## Tests

```bash
pytest
```
