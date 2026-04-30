"""Sync Garmin fitness metrics to the Notion Fitness Summary database."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from garminconnect import Garmin as GarminClient
from notion_client import Client as NotionClient

from garmin_to_notion.config import Settings
from garmin_to_notion.notion_helpers import fetch_all_pages, get_prop

logger = logging.getLogger(__name__)


def _fmt_race_time(seconds: float | None) -> str:
    """Convert race prediction seconds to H:MM:SS or M:SS format."""
    if not seconds:
        return ""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _get_existing_dates(notion: NotionClient, database_id: str) -> dict[str, dict]:
    """Fetch all existing fitness summary entries and return {date_str: page}."""
    pages = fetch_all_pages(notion, database_id)
    result: dict[str, dict] = {}
    for page in pages:
        date_str = get_prop(page["properties"], "Date", "date")
        if date_str:
            result[date_str[:10]] = page
    return result


def _build_properties(
    garmin: GarminClient,
    date_str: str,
) -> dict | None:
    """Build Notion properties from Garmin fitness metrics for a given date."""
    props: dict = {}
    # Training Readiness
    try:
        tr_data = garmin.get_training_readiness(date_str)
        if tr_data:
            # API may return a list or dict
            if isinstance(tr_data, list) and tr_data:
                tr_entry = tr_data[0]
            else:
                tr_entry = tr_data
            score = tr_entry.get("score") or tr_entry.get("trainingReadinessScore")
            level = (
                tr_entry.get("level") or tr_entry.get("trainingReadinessLevel") or ""
            )
            if score:
                props["Training Readiness"] = {"number": round(score)}
            if level:
                props["Training Level"] = {"select": {"name": str(level).upper()}}
    except Exception:
        logger.debug("No training readiness for %s", date_str)
    # VO2 Max
    try:
        max_data = garmin.get_max_metrics(date_str)
        if max_data:
            metrics = (
                max_data
                if isinstance(max_data, list)
                else max_data.get("maxMetList", [])
            )
            for m in (metrics if isinstance(metrics, list) else []):
                sport = m.get("sport", "")
                vo2 = m.get("generic", {}).get("vo2MaxPreciseValue") or m.get(
                    "generic", {}
                ).get("vo2MaxValue")
                if vo2:
                    if sport == "RUNNING":
                        props["VO2 Max (Run)"] = {"number": round(vo2, 1)}
                    elif sport == "CYCLING":
                        props["VO2 Max (Cycle)"] = {"number": round(vo2, 1)}
    except Exception:
        logger.debug("No VO2 max for %s", date_str)
    # Endurance Score
    try:
        es_data = garmin.get_endurance_score(date_str)
        if es_data:
            score = es_data.get("overallScore") or es_data.get("enduranceScore")
            if score:
                props["Endurance Score"] = {"number": round(score)}
    except Exception:
        logger.debug("No endurance score for %s", date_str)
    # Hill Score
    try:
        hs_data = garmin.get_hill_score(date_str)
        if hs_data:
            score = hs_data.get("overallScore") or hs_data.get("hillScore")
            if score:
                props["Hill Score"] = {"number": round(score)}
    except Exception:
        logger.debug("No hill score for %s", date_str)
    # Race Predictions
    try:
        rp_data = garmin.get_race_predictions()
        if rp_data:
            preds = rp_data if isinstance(rp_data, list) else [rp_data]
            for pred in preds:
                dist = pred.get("racePredictionDistanceType", "")
                secs = pred.get("racePredictionInSeconds")
                if dist == "FIVE_KM":
                    props["Race 5K"] = {
                        "rich_text": [{"text": {"content": _fmt_race_time(secs)}}]
                    }
                elif dist == "TEN_KM":
                    props["Race 10K"] = {
                        "rich_text": [{"text": {"content": _fmt_race_time(secs)}}]
                    }
                elif dist == "HALF_MARATHON":
                    props["Race Half"] = {
                        "rich_text": [{"text": {"content": _fmt_race_time(secs)}}]
                    }
                elif dist == "MARATHON":
                    props["Race Marathon"] = {
                        "rich_text": [{"text": {"content": _fmt_race_time(secs)}}]
                    }
    except Exception:
        logger.debug("No race predictions for %s", date_str)
    # Lactate Threshold
    try:
        lt_data = garmin.get_lactate_threshold(latest=True)
        if lt_data:
            shr = lt_data.get("speed_and_heart_rate", {})
            hr = shr.get("heartRate")
            speed = shr.get("speed")
            if hr:
                props["LT Heart Rate"] = {"number": round(hr)}
            if speed:
                props["LT Speed"] = {"number": round(speed, 2)}
    except Exception:
        logger.debug("No lactate threshold for %s", date_str)
    # Running Tolerance
    try:
        rt_data = garmin.get_running_tolerance(date_str, date_str, aggregation="daily")
        if rt_data and isinstance(rt_data, list) and rt_data:
            score = rt_data[0].get("runningTolerance") or rt_data[0].get("overallScore")
            if score:
                props["Running Tolerance"] = {"number": round(score, 1)}
    except Exception:
        logger.debug("No running tolerance for %s", date_str)
    if not props:
        return None
    # Add title and date
    props["Name"] = {"title": [{"text": {"content": date_str}}]}
    props["Date"] = {"date": {"start": date_str}}
    return props


def sync_fitness_summary(
    garmin: GarminClient,
    notion: NotionClient,
    settings: Settings,
    ) -> None:
    """Sync fitness metrics to the Notion Fitness Summary database."""
    if not settings.fitness_summary_db_id:
        logger.info("No fitness summary database configured, skipping")
        return
    logger.info("Fetching existing fitness summary entries from Notion...")
    existing_map = _get_existing_dates(notion, settings.fitness_summary_db_id)
    logger.info("Found %d existing entries in Notion", len(existing_map))
    today = datetime.now(tz=settings.timezone).date()
    created = 0
    skipped = 0
    for i in range(settings.days_back):
        d = today - timedelta(days=i)
        date_str = d.isoformat()
        if date_str in existing_map:
            skipped += 1
            continue
        props = _build_properties(garmin, date_str)
        if not props:
            continue
        time.sleep(1.0)
        notion.pages.create(
            parent={"database_id": settings.fitness_summary_db_id},
            properties=props,
        )
        created += 1
        logger.info("[%d] Created fitness summary: %s", created, date_str)
        if (i + 1) % 50 == 0:
            logger.info("Progress: %d/%d days checked", i + 1, settings.days_back)
    logger.info(
        "Fitness summary sync complete: %d created, %d skipped",
        created,
        skipped,
    )
