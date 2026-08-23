# Task Calendar

Same pattern as the F1 calendar: a script regenerates an `.ics` file, a GitHub
Action runs it on a schedule and commits the result, and you subscribe to the
raw file URL in your calendar app.

## How it works

1. **`docs/task-rules.html`** — open this locally (double-click, works fully
   offline). Add/edit recurring task rules. Click **Download rules.json**
   when you're done editing.
2. **`calendar/rules.json`** — commit the downloaded file to this repo, replacing the
   existing one.
3. **`calendar/generate_tasks.py`** — expands the rules into concrete calendar events
   for a rolling 2-week window (today → +13 days) and writes `calendar/tasks.ics`.
4. **`.github/workflows/update_tasks_calendar.yml`** — runs the script every
   Monday at 05:00 UTC (and any time you push a new `calendar/rules.json`), commits
   `calendar/tasks.ics` if it changed.

## One-time setup

1. Create a GitHub repo (public is simplest, since the raw `.ics` URL needs
   to be fetchable by your calendar app).
2. Add these files at the repo root:
   - `calendar/rules.json`
   - `calendar/generate_tasks.py`
   - `.github/workflows/update_tasks_calendar.yml` (note the folder path)
3. Push. The Action will run automatically on the next Monday, or trigger it
   manually from the **Actions** tab (`Run workflow`) to generate the first
   `calendar/tasks.ics` right away.
4. In your calendar app, subscribe to:
   `https://raw.githubusercontent.com/<you>/<repo>/main/calendar/tasks.ics`

## Updating your tasks

Whenever your recurring tasks change: open `docs/task-rules.html` locally, edit,
download `calendar/rules.json`, and commit/push it to the repo. The push itself
triggers a regeneration (no need to wait for Monday).

## Notes

- Each event's UID is stable (`task-<rule id>-<date>`), so re-syncing
  doesn't create duplicates — your calendar app just updates in place.
- Categories (chore/work/health/finance/personal) get a small emoji prefix
  in the event title so they're easy to tell apart in a list view.
- "Once" rules are for one-off dated tasks that don't repeat.
- The window is 14 days by default — change `--days` in the workflow step
  if you want more or less runway.
