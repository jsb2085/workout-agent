# Notion import

This folder is the Workout Agent UI. Import it into Notion, then share the page with your integration.

## Fastest: create it from this repo

1. Create an internal integration: https://www.notion.so/my-integrations
2. Copy the token into `.env` as `NOTION_TOKEN`
3. In Notion, make any page (or use an existing one) and **Share → Invite** that integration
4. Copy the page URL and run:

```bash
workout setup --parent "https://www.notion.so/your-page-...." --write-env
```

That creates a **Workout Agent** child page — cover, how-to, section headers, and a caption above each of the six inline databases — plus example Goals / Location / Body Stats rows, and writes the database ids into `.env`.

Open that page in Notion. New row = New item. You edit **Goals**, **Workout Locations**, and **Body Stats**. After you train, fill **Actual weight** on **Workout Lifts**, then `workout run`.

## Import the CSVs by hand

If you would rather not run the CLI:

1. Download the files in [`csv/`](csv/) from GitHub (or clone this repo)
2. In Notion, open a page → **Import → CSV** for each file
3. After import, set property types to match the table below (CSV import often leaves everything as text)
4. Share each database with your integration
5. Copy each database id into `.env`

| CSV | Notion database | You edit? | Types to set |
|---|---|---|---|
| `goals.csv` | Goals | Yes | Deadline = date, Status = select (Active / Paused / Done) |
| `workout_locations.csv` | Workout Locations | Yes | Default = checkbox |
| `body_stats.csv` | Body Stats | Yes | Date = date |
| `workout_lifts.csv` | Workout Lifts | Actual weight after you lift | Date + Week start = date, Reps = number, Completed = checkbox |
| `daily_logs.csv` | Daily Logs | Optional | Date = date, checkboxes + numbers as named |
| `weekly_workouts.csv` | Weekly Workouts | No — planner publishes here | Week = date, Status = select (Planned / In progress / Done) |

Schema source of truth: [`app/notion_import/schema.json`](../app/notion_import/schema.json).
