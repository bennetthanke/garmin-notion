# Garmin to Notion

Sync your Garmin fitness data to Notion databases. Fully automated via GitHub Actions, 3 times a day.

> **This is a fork of [fly-labs/garmin-to-notion](https://github.com/fly-labs/garmin-to-notion)** with enhancements — see [Fork Enhancements](#fork-enhancements) below.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Sync: GitHub Actions](https://img.shields.io/badge/sync-GitHub%20Actions-purple)

## Fork Enhancements

This fork adds the following on top of the original:

### New Database: Fitness Summary
- **Training Readiness** — Garmin's daily readiness score (0–100)
- **Training Level** — PRIME / HIGH / MODERATE / LOW / POOR classification
- **LT Heart Rate** — Lactate threshold heart rate
- **Race Predictions** — Estimated 5K, 10K, Half Marathon, and Marathon times

### Enhanced Sleep Tracking
- **Stress data** — `Stress Avg` and `Stress Max` per night (uses `avgStressLevel` from Garmin API — note: `overallStressLevel` returns NULL)
- **HRV data** — `HRV Avg` (heart rate variability) and `HRV Status` (BALANCED / LOW / UNBALANCED / POOR)
- **SpO2** — Blood oxygen saturation percentage
- **Respiration** — Average respiration rate
- **Bed Time / Wake Time** — Sleep and wake timestamps
- **Computed Sleep Score** — Custom quality score (1–100) based on:
  - Duration (40%): 100 if 7–9h, linear ramp 4h→7h and 9h→11h
  - Deep Sleep % (25%): optimal ~20%, drops 4 pts per 1% deviation
  - REM % (25%): optimal ~22%, drops 4 pts per 1% deviation
  - Awake Penalty (10%): 0 min = 100, 30+ min = 0

### Enhanced Activity Tracking
- **VO2 Max** — Per-activity VO2 Max reading (when reported by Garmin)
- **VO2 Type** — Formula property that categorizes as "Running" or "Cycling" for split trend analysis
- **Hour Block** — 2-hour time window (e.g. `16:00-18:00`) for workout timing analysis
- **Day of Week** — For weekly pattern analysis

### Notion Template with 18+ Chart Views
The Notion AI prompt creates a complete dashboard with:
- **Trend lines** — Sleep Score, Garmin Score, Stress, HRV, Resting HR, VO2 Max (split by Running/Cycling), Training Readiness
- **Distribution donuts** — Activity type, Calories by sport, Distance by sport, Workout time of day, HRV Status, Training Level
- **Correlation charts** — Sleep vs Stress, HRV by Stress Level, Avg HR by Activity Type, Calories by Day of Week
- **Weekly Training Load** — Calorie-based weekly volume tracking
- All charts include descriptive captions

### Bug Fixes
- Fixed Garmin stress API key: `avgStressLevel` (not `overallStressLevel`, which returns NULL)

### Performance
- **Configurable summary window** — by default the Activity Summary sync only recomputes the current and previous month plus the current year, instead of every month/year bucket since you started tracking. Cuts a typical sync from ~5 minutes to ~30 seconds. Tune via `SUMMARY_WINDOW_MONTHS` (default `2`, set to `9999` for a full rebuild).

## Features

- **Activities** — distance, pace, power, HR, training effect, VO2 Max, with emoji icons and heatmap properties
- **Personal Records** — fastest 1K, 5K, 10K, longest run/ride, and more
- **Daily Steps** — step count, goal, distance
- **Sleep** — duration, deep/light/REM/awake stages, resting HR, HRV, stress, SpO2, computed quality score
- **Fitness Summary** — daily training readiness, training level, LT heart rate, race predictions *(new in this fork)*
- **Workouts** — categorized workout log with modality and intensity derived from activities
- **Activity Summary** — monthly and yearly aggregations with lifestyle averages (sleep, steps, HR)
- **60+ activity types** — running, cycling, swimming, strength, BJJ, climbing, winter sports, and more
- **Auto-discovery** — finds your Notion databases by name, no manual IDs needed
- **Timezone-aware** — configurable via `TIMEZONE` variable, all timestamps are correct
- **Zero-touch automation** — runs 3x/day via GitHub Actions (free tier friendly)

## Setup Guide

### Step 1: Fork this repository

Click **Fork** on GitHub to create your own copy.

### Step 2: Set up your Notion template

**Option A — Notion AI (recommended):**
1. Open a new Notion page
2. Copy the full contents of [`docs/notion-ai-prompt.txt`](docs/notion-ai-prompt.txt)
3. Paste it into Notion AI — it will create the complete template with all 6 databases, 18+ chart views, and board/calendar views
4. Follow the post-creation checklist in [`docs/notion-template-setup.md`](docs/notion-template-setup.md) to convert date filters to relative

**Option B — Duplicate template:**
Coming soon — a public template you can duplicate in one click.

### Step 3: Create Notion integration

1. Go to [notion.so/profile/integrations](https://www.notion.so/profile/integrations)
2. Click **New integration** → name it "Garmin Sync" → select **Internal**
3. Copy the integration token (starts with `ntn_`)
4. Go to your **Fitness Tracker** page in Notion → click `...` → **Connect to** → **Garmin Sync**

All inline databases inherit access automatically — no need to connect each one individually.

### Step 4: Add GitHub Secrets

Go to your fork's **Settings → Secrets and variables → Actions → Secrets** and add:

| Secret | Description |
|---|---|
| `GARMIN_EMAIL` | Your Garmin Connect email |
| `GARMIN_PASSWORD` | Your Garmin Connect password |
| `NOTION_TOKEN` | Your Notion integration token |

### Step 5: Set Variables (optional)

Go to **Settings → Secrets and variables → Actions → Variables** and add:

| Variable | Default | Description |
|---|---|---|
| `TIMEZONE` | `UTC` | Your IANA timezone (e.g. `America/New_York`, `Europe/London`) |
| `GARMIN_DAYS_BACK` | `30` | Days of sleep/steps history to sync |
| `SUMMARY_WINDOW_MONTHS` | `2` | How many recent months the Activity Summary recomputes (set `9999` for a full rebuild) |

### Step 6: Run!

Go to the **Actions** tab → **Garmin to Notion Sync** → **Run workflow**.

Your data will appear in Notion within a few minutes. After that, the sync runs automatically 3 times a day.

## How It Works

​
Garmin Connect API
│
├──→ Activities DB ──→ Workouts DB ──┐
├──→ Personal Records DB             ├──→ Activity Summary DB
├──→ Daily Steps DB ─────────────────┘         (monthly/yearly)
├──→ Sleep DB
└──→ Fitness Summary DB (new)

Activities, Personal Records, Daily Steps, Sleep, and Fitness Summary are synced independently from the Garmin API. Workouts are derived from Activities. Activity Summary aggregates data from Workouts, Daily Steps, and Sleep into monthly and yearly overviews.

## Supported Activities

| Category | Activities | Tracked Metrics |
|---|---|---|
| Running | Running, Treadmill, Trail, Track, Ultra | Distance, Pace, HR, Training Effect, VO2 Max |
| Cycling | Outdoor, Indoor, Mountain Biking, Gravel, E-Bike | Distance, Power, Duration, VO2 Max |
| Swimming | Lap Swimming, Open Water | Distance, Duration, Calories |
| Strength & Fitness | Strength Training, Crossfit, Functional Training, HIIT | Duration, Calories, Training Effect |
| Combat | BJJ / MMA, Boxing, Kickboxing | Duration, Calories, Intensity |
| Racquet Sports | Tennis, Padel, Badminton, Pickleball, Squash, Table Tennis | Duration, Calories |
| Team Sports | Soccer, Basketball, Volleyball, Football, Rugby, Hockey | Duration, Calories |
| Winter Sports | Skiing, Snowboarding, Cross Country Skiing, Ice Skating | Duration, Distance, Calories |
| Water Sports | Kayaking, Surfing, Stand Up Paddleboarding | Duration, Distance |
| Climbing | Rock Climbing, Bouldering, Indoor Climbing, Mountaineering | Duration, Calories |
| Walking | Walking, Hiking, Speed Walking | Steps, Distance |
| Yoga & Mindfulness | Yoga, Pilates, Stretching, Meditation | Duration, Calories |
| Rowing | Rowing, Indoor Rowing | Distance, Power, Duration |
| Other | Golf, Dance, Skateboarding, Multi Sport, Triathlon | Duration, Calories |

## Configuration

### GitHub Secrets (required)

| Secret | Description |
|---|---|
| `GARMIN_EMAIL` | Your Garmin Connect email |
| `GARMIN_PASSWORD` | Your Garmin Connect password |
| `NOTION_TOKEN` | Your Notion integration token |

### GitHub Variables (optional)

| Variable | Default | Description |
|---|---|---|
| `TIMEZONE` | `UTC` | IANA timezone for activity timestamps |
| `GARMIN_DAYS_BACK` | `30` | Days of sleep/steps history to sync |
| `SUMMARY_WINDOW_MONTHS` | `2` | Months of history the Activity Summary recomputes per run (set `9999` to rebuild every period) |

### Database IDs (optional — auto-discovered by default)

If auto-discovery doesn't work, you can set these as secrets:

| Secret | Database |
|---|---|
| `NOTION_DB_ID` | Activities |
| `NOTION_PR_DB_ID` | Personal Records |
| `NOTION_STEPS_DB_ID` | Daily Steps |
| `NOTION_SLEEP_DB_ID` | Sleep |
| `NOTION_WORKOUTS_DB_ID` | Workouts |
| `NOTION_SUMMARY_DB_ID` | Activity Summary |

## Running Locally

​
Install dependencies
pip install -r requirements.txt
Copy and configure environment
cp .env.example .env
Edit .env with your credentials
Run all syncs
PYTHONPATH=src python -m garmin_to_notion all
Run a specific sync
PYTHONPATH=src python -m garmin_to_notion activities
PYTHONPATH=src python -m garmin_to_notion records
PYTHONPATH=src python -m garmin_to_notion steps
PYTHONPATH=src python -m garmin_to_notion sleep
PYTHONPATH=src python -m garmin_to_notion fitness_summary
PYTHONPATH=src python -m garmin_to_notion workouts
PYTHONPATH=src python -m garmin_to_notion summary
Cleanup duplicate workouts (dry run first)
PYTHONPATH=src python -m garmin_to_notion cleanup
PYTHONPATH=src python -m garmin_to_notion cleanup --execute
Verbose output
PYTHONPATH=src python -m garmin_to_notion all -v

**Windows (PowerShell):**
​
cd C:UsersbhankeProjectsgarmin-notion
$env:PYTHONPATH="src"
python -m garmin_to_notion all

## Project Structure

​
src/garmin_to_notion/
init.py          # Package version
main.py          # CLI entry point
config.py            # Settings and env validation
clients.py           # Garmin + Notion client setup
log.py               # Logging configuration
notion_helpers.py    # Shared Notion utilities
formatters.py        # Data formatting (pace, duration, etc.)
mappings.py          # Activity emojis, modality maps, constants
syncers/
activities.py        # Garmin → Activities DB
personal_records.py  # Garmin → Personal Records DB
daily_steps.py       # Garmin → Daily Steps DB
sleep.py             # Garmin → Sleep DB
fitness_summary.py   # Garmin → Fitness Summary DB (new)
workouts.py          # Activities DB → Workouts DB
summary.py           # Workouts+Steps+Sleep → Activity Summary DB
tools/
cleanup_duplicates.py  # Deduplicate Workouts DB

## Troubleshooting

### Charts show errors
Run the Notion AI update prompt ([`docs/notion-ai-update-prompt.txt`](docs/notion-ai-update-prompt.txt)) to recreate all views and charts. Make sure your databases have data first — charts won't render on empty databases.

### Wrong activity times
Set the `TIMEZONE` variable to your IANA timezone (e.g. `America/New_York`). If you already have activities with wrong times, re-run `python -m garmin_to_notion activities` — it will detect and fix timezone mismatches automatically.

### Calendar views show empty months
Notion calendar views require a Date property. If a month appears empty, check that the sync has run and populated data for that period. For sleep and steps, increase `GARMIN_DAYS_BACK` to backfill older data.

### Activity Summary shows zero steps or sleep
Activity Summary aggregates from Workouts, Daily Steps, and Sleep databases. Make sure all three syncs have run at least once. Run `python -m garmin_to_notion all` to sync everything, then `python -m garmin_to_notion summary` to regenerate summaries.

### Activity Summary missing old months after backfilling activities
By default the summary sync only recomputes the last 2 months plus the current year. If you backfilled older activities, force a one-time full rebuild by setting `SUMMARY_WINDOW_MONTHS=9999` (as a repo Variable or local env var) and running the sync. Set it back to `2` afterward.

### Sleep sync is slow on first run
The first sync fetches `GARMIN_DAYS_BACK` days of sleep data (default 30). For large backfills (e.g. `GARMIN_DAYS_BACK=3650`), the first run calls the Garmin API for each day without existing data. Subsequent syncs skip existing dates and are near-instant.

### Stress data shows NULL
The Garmin API key for daily stress is `avgStressLevel`, **not** `overallStressLevel` (which returns NULL). This is already fixed in this fork.

### Auto-discovery can't find databases
Make sure the Notion integration is connected to the **Fitness Tracker** page (not individual databases). Database names must match exactly: **Activities**, **Personal Records**, **Daily Steps**, **Sleep**, **Fitness Summary**, **Workouts**, **Activity Summary**.

### Rate limiting (HTTP 429)
If you hit Garmin's rate limit, stop all sync attempts and wait 2–3 hours before retrying.

## Acknowledgements

This project builds on the work of [Chloe Voyer](https://github.com/chloevoyer/garmin-to-notion), who created the original Garmin-to-Notion sync, and the extended version by [FlyLabs](https://github.com/fly-labs/garmin-to-notion). This fork adds Fitness Summary tracking, enhanced sleep metrics (HRV, stress, SpO2), VO2 Max tracking, a computed sleep score, and a full Notion dashboard with 18+ chart views.

Other projects that inspired this work:
- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) — Garmin API wrapper
- [n-kratz/garmin-notion](https://github.com/n-kratz/garmin-notion) — alternative Garmin-Notion integration

## License

MIT License. See [LICENSE](LICENSE) for details.
