"""Sync Garmin daily step counts to the Notion Steps database."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from garminconnect import Garmin as GarminClient
from notion_client import Client as NotionClient

from garmin_to_notion.config import Settings

logger = logging.getLogger(__name__)


def _get_steps_range(garmin: GarminClient, days_back: int, tz: ZoneInfo) -> list[dict]:
    """Fetch step counts for the last *days_back* days (excluding today)."""
    end_date = datetime.now(tz=tz).date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days_back - 1)
    return garmin.get_daily_steps(start_date.isoformat(), end_date.isoformat())


def _steps_exist(
    notion: NotionClient,
    database_id: str,
    activity_date: str,
) -> dict | None:
    """Check if a daily steps entry already exists for the given date."""
    query = notion.databases.query(
        database_id=database_id,
        filter={"property": "Date", "date": {"equals": activity_date}},
    )
    results = query["results"]
    return results[0] if results else None


def _steps_need_update(existing: dict, new_steps: dict) -> bool:
    """Compare existing steps data with new data to detect changes."""
    props = existing["properties"]
    total_steps = new_steps.get("totalSteps") or 0
    current_title = props.get("Name", {}).get("title", [])
    current_name = current_title[0]["text"]["content"] if current_title else ""
    return (
        current_name != f"{total_steps:,} steps"
        or props["Steps"]["number"] != total_steps
        or props["Goal"]["number"] != new_steps.get("stepGoal")
        or props["Distance (km)"]["number"]
        != round((new_steps.get("totalDistance") or 0) / 1000, 2)
    )


def _build_properties(steps: dict) -> dict:
    """Build Notion properties from step data."""
    total_steps = steps.get("totalSteps") or 0
    total_distance = steps.get("totalDistance") or 0
    return {
        "Name": {"title": [{"text": {"content": f"{total_steps:,} steps"}}]},
        "Date": {"date": {"start": steps.get("calendarDate")}},
        "Steps": {"number": total_steps},
        "Goal": {"number": steps.get("stepGoal")},
        "Distance (km)": {"number": round(total_distance / 1000, 2)},
    }


def sync_daily_steps(
    garmin: GarminClient,
    notion: NotionClient,
    settings: Settings,
) -> None:
    """Sync historical daily step counts to the Notion Steps database."""
    if not settings.steps_db_id:
        logger.info("No steps database configured, skipping")
        return

    daily_steps = _get_steps_range(garmin, settings.days_back, settings.timezone)
    logger.info("Fetched %d step entries from Garmin", len(daily_steps))

    if daily_steps:
        sample = daily_steps[0]
        logger.debug("Sample step entry keys: %s", list(sample.keys()))
        logger.debug("Sample: date=%s steps=%s goal=%s",
            sample.get("calendarDate"), sample.get("totalSteps"), sample.get("stepGoal"))

    # Pre-fetch existing dates to skip without API calls
    existing_dates = {}
    cursor = None
    while True:
        qargs = {"database_id": settings.steps_db_id, "page_size": 100}
        if cursor:
            qargs["start_cursor"] = cursor
        res = notion.databases.query(**qargs)
        for pg in res["results"]:
            date_prop = pg["properties"].get("Date", {}).get("date")
            if date_prop and date_prop.get("start"):
                existing_dates[date_prop["start"][:10]] = pg
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
        time.sleep(0.5)
    logger.info("Pre-fetched %d existing step entries", len(existing_dates))
    created, updated, skipped = 0, 0, 0

    for steps in daily_steps:
        steps_date = steps.get("calendarDate")
        existing = existing_dates.get(steps_date)
        if existing:
            if _steps_need_update(existing, steps):
                time.sleep(1.0)
                props = _build_properties(steps)
                del props["Date"]  # Don't update the date
                notion.pages.update(page_id=existing["id"], properties=props)
                updated += 1
                logger.info(
                    "[%d/%d] Updated: %s",
                    created + updated + skipped, len(daily_steps), steps_date,
                )
            else:
                skipped += 1
        else:
            time.sleep(1.0)
            props = _build_properties(steps)
            notion.pages.create(
                parent={"database_id": settings.steps_db_id},
                properties=props,
            )
            created += 1
            logger.info(
                "[%d/%d] Created: %s (skipped %d existing)",
                created + updated + skipped, len(daily_steps), steps_date, skipped,
            )

    if created > 0 and all((s.get("totalSteps") or 0) == 0 for s in daily_steps):
        logger.warning("All step entries have 0 steps — check Garmin sync or watch permissions")

    logger.info(
        "Daily steps sync complete: %d created, %d updated, %d unchanged",
        created, updated, skipped,
    )
