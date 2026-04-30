"""Sync Garmin activities to the Notion Activities database."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
import time

from garminconnect import Garmin as GarminClient
from notion_client import Client as NotionClient

from garmin_to_notion.config import Settings
from garmin_to_notion.formatters import (
    format_activity_type,
    format_duration,
    format_effect_rich,
    format_pace,
    format_training_effect,
    gmt_to_local,
)
from garmin_to_notion.mappings import ACTIVITY_EMOJIS

logger = logging.getLogger(__name__)


def _build_properties(activity: dict, settings: Settings) -> dict:
    """Build the Notion properties payload from a Garmin activity."""
    activity_name = activity.get("activityName", "Unnamed Activity")
    activity_type, activity_subtype = format_activity_type(
        activity.get("activityType", {}).get("typeKey", "Unknown"),
        activity_name,
    )
    local_date = gmt_to_local(activity.get("startTimeGMT"), settings.timezone)

    # Heatmap properties
    day_of_week = local_date.strftime("%A")
    hour = local_date.hour
    block_start = (hour // 2) * 2
    hour_block = f"{block_start:02d}:00-{block_start + 2:02d}:00"

    return {
        "Date": {"date": {"start": local_date.isoformat()}},
        "Type": {"select": {"name": activity_type}},
        "SubType": {"select": {"name": activity_subtype}},
        "Name": {"title": [{"text": {"content": activity_name}}]},
        "Distance (km)": {"number": round(activity.get("distance", 0) / 1000, 2)},
        "Duration": {
            "rich_text": [
                {"text": {"content": format_duration(activity.get("duration", 0))}}
            ]
        },
        "Calories": {"number": round(activity.get("calories", 0))},
        "Avg Pace": {
            "rich_text": [
                {"text": {"content": format_pace(activity.get("averageSpeed", 0))}}
            ]
        },
        "Avg HR": {"number": round(activity.get("averageHR", 0) or 0)},
        "Max HR": {"number": round(activity.get("maxHR", 0) or 0)},
        "Avg Power": {"number": round(activity.get("avgPower", 0) or 0, 1)},
        "Training Effect": {
            "rich_text": [
                {
                    "text": {
                        "content": format_training_effect(
                            activity.get("trainingEffectLabel", "Unknown")
                        )
                    }
                }
            ]
        },
        "Aerobic Effect": {
            "rich_text": [
                {
                    "text": {
                        "content": format_effect_rich(
                            activity.get("aerobicTrainingEffect", 0) or 0,
                            activity.get("aerobicTrainingEffectMessage", "Unknown"),
                        )
                    }
                }
            ]
        },
        "Anaerobic Effect": {
            "rich_text": [
                {
                    "text": {
                        "content": format_effect_rich(
                            activity.get("anaerobicTrainingEffect", 0) or 0,
                            activity.get("anaerobicTrainingEffectMessage", "Unknown"),
                        )
                    }
                }
            ]
        },
        "Steps": {"number": activity.get("steps", 0) or 0},
        "Garmin ID": {"number": activity.get("activityId")},
        "Day of Week": {"select": {"name": day_of_week}},
        "Hour Block": {"select": {"name": hour_block}},
        "VO2 Max": {"number": activity.get("vO2MaxValue")},
    }


def _get_icon_emoji(activity: dict) -> str:
    """Get the emoji icon for an activity based on its type."""
    activity_name = activity.get("activityName", "")
    _, activity_subtype = format_activity_type(
        activity.get("activityType", {}).get("typeKey", "Unknown"),
        activity_name,
    )
    return ACTIVITY_EMOJIS.get(activity_subtype, ACTIVITY_EMOJIS["Other"])


def _activity_exists(
    notion: NotionClient,
    database_id: str,
    garmin_id: int | None,
    activity_date: datetime,
    activity_type: str,
    activity_name: str,
) -> dict | None:
    """Check if an activity already exists in the Notion database.

    Primary lookup: by Garmin ID (unique). Fallback: date + type + name.
    """
    if garmin_id:
        query = notion.databases.query(
            database_id=database_id,
            filter={"property": "Garmin ID", "number": {"equals": garmin_id}},
        )
        if query["results"]:
            return query["results"][0]

    # Fallback for legacy entries without Garmin ID
    lookup_type = (
        "Stretching" if "stretch" in activity_name.lower() else activity_type
    )
    lookup_min = activity_date - timedelta(minutes=5)
    lookup_max = activity_date + timedelta(minutes=5)

    query = notion.databases.query(
        database_id=database_id,
        filter={
            "and": [
                {
                    "property": "Date",
                    "date": {"on_or_after": lookup_min.isoformat()},
                },
                {
                    "property": "Date",
                    "date": {"on_or_before": lookup_max.isoformat()},
                },
                {"property": "Type", "select": {"equals": lookup_type}},
                {"property": "Name", "title": {"equals": activity_name}},
            ]
        },
    )
    results = query["results"]
    return results[0] if results else None


def _activity_needs_update(
    existing: dict, new_activity: dict, settings: Settings
) -> bool:
    """Compare an existing Notion page with new Garmin data to detect changes."""
    props = existing["properties"]

    try:
        existing_date = props["Date"]["date"]["start"]
        new_date = gmt_to_local(
            new_activity.get("startTimeGMT"), settings.timezone
        ).isoformat()
        date_changed = existing_date != new_date

        distance_changed = (
            props["Distance (km)"]["number"]
            != round(new_activity.get("distance", 0) / 1000, 2)
        )
        calories_changed = (
            props["Calories"]["number"] != round(new_activity.get("calories", 0))
        )
        pace_changed = (
            props["Avg Pace"]["rich_text"][0]["text"]["content"]
            != format_pace(new_activity.get("averageSpeed", 0))
        )
        hr_changed = (
            props["Avg HR"]["number"] != round(new_activity.get("averageHR", 0) or 0)
            or props["Max HR"]["number"]
            != round(new_activity.get("maxHR", 0) or 0)
        )
        return (
            date_changed or distance_changed or calories_changed
            or pace_changed or hr_changed
        )
    except (KeyError, TypeError, IndexError):
        return True


def sync_activities(
    garmin: GarminClient,
    notion: NotionClient,
    settings: Settings,
) -> None:
    """Sync all Garmin activities to the Notion Activities database."""
    activities = garmin.get_activities(0, settings.fetch_limit)
    logger.info("Fetched %d activities from Garmin", len(activities))

    # Pre-fetch all existing Garmin IDs to avoid redundant API lookups
    existing_ids = set()
    cursor = None
    while True:
        qargs = {"database_id": settings.activities_db_id, "page_size": 100}
        if cursor:
            qargs["start_cursor"] = cursor
        res = notion.databases.query(**qargs)
        for pg in res["results"]:
            gid = pg["properties"].get("Garmin ID", {}).get("number")
            if gid:
                existing_ids.add(gid)
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
        time.sleep(0.5)
    logger.info("Pre-fetched %d existing activity IDs", len(existing_ids))
    
    # TEMPORARY: backfill VO2 Max on existing activities
    if False:  # Change to False after running once
            logger.info("Backfilling VO2 Max on existing activities...")
            repaired = 0
            for activity in activities:
                    garmin_id = activity.get("activityId")
                    vo2 = activity.get("vO2MaxValue")
                    if not garmin_id or not vo2:
                            continue
                    if garmin_id not in existing_ids:
                            continue
                    query = notion.databases.query(
                            database_id=settings.activities_db_id,
                            filter={"property": "Garmin ID", "number": {"equals": garmin_id}},
                    )
                    if query["results"]:
                            time.sleep(0.5)
                            notion.pages.update(
                                    page_id=query["results"][0]["id"],
                                    properties={"VO2 Max": {"number": vo2}},
                            )
                            repaired += 1
                            if repaired % 20 == 0:
                                    logger.info("Backfilled %d activities", repaired)
            logger.info("VO2 Max backfill complete: %d updated", repaired)
            return

    created, updated, skipped = 0, 0, 0

    for activity in activities:
        if activity.get("activityId") in existing_ids:
            skipped += 1
            continue
        time.sleep(1.0)
        activity_name = activity.get("activityName", "Unnamed Activity")
        logger.info(
            "[%d/%d] Syncing: %s (skipped %d existing)",
            created + updated + skipped + 1,
            len(activities),
            activity_name,
            skipped,
        )
        activity_type, _ = format_activity_type(
            activity.get("activityType", {}).get("typeKey", "Unknown"),
            activity_name,
        )
        activity_date = gmt_to_local(activity.get("startTimeGMT"), settings.timezone)
        garmin_id = activity.get("activityId")

        existing = _activity_exists(
            notion, settings.activities_db_id,
            garmin_id, activity_date, activity_type, activity_name,
        )

        if existing:
            if _activity_needs_update(existing, activity, settings):
                props = _build_properties(activity, settings)
                emoji = _get_icon_emoji(activity)
                notion.pages.update(
                    page_id=existing["id"],
                    properties=props,
                    icon={"emoji": emoji},
                )
                updated += 1
            else:
                skipped += 1
        else:
            props = _build_properties(activity, settings)
            emoji = _get_icon_emoji(activity)
            notion.pages.create(
                parent={"database_id": settings.activities_db_id},
                properties=props,
                icon={"emoji": emoji},
            )
            created += 1
            logger.info("[%d/%d] Created activity: %s", created + updated, len(activities), activity_name)

    logger.info(
        "Activities sync complete: %d created, %d updated, %d unchanged",
        created,
        updated,
        skipped,
    )