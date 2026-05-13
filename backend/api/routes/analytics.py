from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import json
import logging

from backend.core.database import Database
from backend.app.analytics.topic_extractor import (
    extract_topics_from_research_sessions,
    extract_topics_from_journal,
    extract_topics_from_files,
    aggregate_all_topics,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

# Initialize database instance
db = Database()


def calculate_trend_indicator(current: int, previous: int) -> str:
    """Calculate trend indicator (↑, ↓, →, ~)."""
    if previous == 0:
        return "→" if current == 0 else "↑"

    change_pct = ((current - previous) / previous) * 100

    if change_pct > 20:
        return "↑"  # Significantly up
    elif change_pct < -20:
        return "↓"  # Significantly down
    elif abs(change_pct) < 5:
        return "→"  # Stable
    else:
        return "~"  # Slight change


@router.get("/topics")
async def get_topics(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 180d, 365d"),
    source: str = Query("all", description="Source: research, journal, files, all"),
) -> Dict[str, Any]:
    """
    Get topic frequencies with trend indicators.
    Sources: research sessions, journal entries, and indexed files.
    """
    try:
        # Parse period
        if not period.endswith("d"):
            raise HTTPException(
                status_code=400, detail="Period must end with 'd' (e.g., 30d)"
            )

        period_days = int(period[:-1])
        if period_days <= 0:
            raise HTTPException(status_code=400, detail="Period days must be positive")

        # Generate cache key
        cache_key = f"topics:{source}:{period}"
        user_id = "user"  # Default user_id for now

        # Check cache
        cached_data = await db.get_analytics_snapshot(user_id, cache_key)
        if cached_data:
            return cached_data

        # Extract topics based on source
        if source == "all":
            all_topics = await aggregate_all_topics(period_days)
        elif source == "research":
            all_topics = await extract_topics_from_research_sessions(period_days)
        elif source == "journal":
            all_topics = await extract_topics_from_journal(period_days)
        elif source == "files":
            all_topics = await extract_topics_from_files(period_days)
        else:
            raise HTTPException(status_code=400, detail="Invalid source parameter")

        # Get previous period data for trend calculation
        prev_period_days = period_days * 2
        if source == "all":
            prev_topics = await aggregate_all_topics(prev_period_days)
            # Filter to get only the first half (the older period)
            cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
            prev_topics = [
                t
                for t in prev_topics
                if datetime.fromisoformat(t.get("first_seen", "2000-01-01")) < cutoff
            ][: len(prev_topics) // 2]
        elif source == "research":
            prev_topics = await extract_topics_from_research_sessions(prev_period_days)
        elif source == "journal":
            prev_topics = await extract_topics_from_journal(prev_period_days)
        else:
            prev_topics = await extract_topics_from_files(prev_period_days)

        # Create a dict of previous topic counts for fast lookup
        prev_topic_counts = {t["topic"]: t["count"] for t in prev_topics}

        # Add trend indicators
        enhanced_topics = []
        for topic_data in all_topics:
            topic = topic_data["topic"]
            current_count = topic_data["count"]
            prev_count = prev_topic_counts.get(topic, 0)

            trend = calculate_trend_indicator(current_count, prev_count)

            enhanced_topics.append(
                {
                    "topic": topic,
                    "count": current_count,
                    "sources": topic_data.get("sources", [source]),
                    "trend": trend,
                }
            )

        # Sort by count descending
        enhanced_topics.sort(key=lambda x: x["count"], reverse=True)

        response = {
            "period": period,
            "source": source,
            "topics": enhanced_topics[:100],  # Top 100 overall
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache the result
        await db.set_analytics_snapshot(user_id, cache_key, response, ttl_seconds=21600)

        return response
    except Exception as e:
        logger.error("Error getting topics: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze topics: {str(e)}"
        )


@router.get("/blind-spots")
async def get_blind_spots(
    period: str = Query("90d", description="Period: 30d, 90d, 180d, 365d"),
    min_research_count: int = Query(
        3, description="Minimum research mentions to qualify"
    ),
) -> Dict[str, Any]:
    """
    Identify blind spots: topics researched frequently but rarely/never journaled about.
    """
    try:
        # Parse period
        if not period.endswith("d"):
            raise HTTPException(status_code=400, detail="Period must end with 'd'")

        period_days = int(period[:-1])
        if period_days <= 0:
            raise HTTPException(status_code=400, detail="Period days must be positive")

        # Generate cache key
        cache_key = f"blind-spots:{period}:{min_research_count}"
        user_id = "user"

        # Check cache
        cached_data = await db.get_analytics_snapshot(user_id, cache_key)
        if cached_data:
            return cached_data

        # Extract topics from both sources
        research_topics = await extract_topics_from_research_sessions(period_days)
        journal_topics = await extract_topics_from_journal(period_days)

        # Create sets for comparison
        research_topic_counts = {t["topic"]: t["count"] for t in research_topics}
        journal_topic_set = {t["topic"] for t in journal_topics}

        # Find blind spots: researched >= min_research_count, journaled < 1
        blind_spots = []
        for topic, count in research_topic_counts.items():
            if count >= min_research_count and topic not in journal_topic_set:
                blind_spots.append(
                    {
                        "topic": topic,
                        "research_count": count,
                        "journal_count": 0,
                        "significance": "high" if count >= 5 else "medium",
                    }
                )

        # Sort by research count (descending)
        blind_spots.sort(key=lambda x: x["research_count"], reverse=True)

        response = {
            "period": period,
            "potential_blind_spots": blind_spots[:50],  # Top 50
            "total_research_topics": len(research_topics),
            "total_journal_topics": len(journal_topics),
            "blind_spot_count": len(blind_spots),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache the result
        await db.set_analytics_snapshot(user_id, cache_key, response, ttl_seconds=21600)

        return response
    except Exception as e:
        logger.error("Error getting blind spots: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to detect blind spots: {str(e)}"
        )


@router.get("/research-velocity")
async def get_research_velocity(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 180d, 365d"),
    interval: str = Query("week", description="Aggregation interval: day, week"),
) -> Dict[str, Any]:
    """
    Track research velocity: sessions started and completed per time interval.
    """
    try:
        # Parse period
        if not period.endswith("d"):
            raise HTTPException(status_code=400, detail="Period must end with 'd'")

        period_days = int(period[:-1])
        if period_days <= 0:
            raise HTTPException(status_code=400, detail="Period days must be positive")

        # Generate cache key
        cache_key = f"research-velocity:{period}:{interval}"
        user_id = "user"

        # Check cache
        cached_data = await db.get_analytics_snapshot(user_id, cache_key)
        if cached_data:
            return cached_data

        # Query research sessions
        from sqlalchemy import extract
        from backend.core.database import ResearchSession

        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        async with get_session() as session:
            stmt = select(ResearchSession).where(
                ResearchSession.created_at >= cutoff, ResearchSession.status != "failed"
            )
            result = await session.execute(stmt)
            sessions = result.scalars().all()

        # Group by interval
        velocity_data = []

        if interval == "week":
            # Group by ISO week
            weekly_data = {}
            for session in sessions:
                if session.started_at:
                    week_key = session.started_at.isocalendar()[:2]  # (year, week)
                    if week_key not in weekly_data:
                        weekly_data[week_key] = {"started": 0, "completed": 0}
                    weekly_data[week_key]["started"] += 1

                    if session.completed_at and session.status == "done":
                        weekly_data[week_key]["completed"] += 1

            # Convert to list format
            for (year, week), counts in sorted(weekly_data.items()):
                completion_rate = (
                    counts["completed"] / counts["started"] * 100
                    if counts["started"] > 0
                    else 0
                )
                velocity_data.append(
                    {
                        "interval": f"{year}-W{week:02d}",
                        "started": counts["started"],
                        "completed": counts["completed"],
                        "completion_rate": round(completion_rate, 1),
                    }
                )

        elif interval == "day":
            # Group by day
            daily_data = {}
            for session in sessions:
                if session.started_at:
                    day_key = session.started_at.date().isoformat()
                    if day_key not in daily_data:
                        daily_data[day_key] = {"started": 0, "completed": 0}
                    daily_data[day_key]["started"] += 1

                    if session.completed_at and session.status == "done":
                        daily_data[day_key]["completed"] += 1

            # Convert to list format
            for day, counts in sorted(daily_data.items()):
                completion_rate = (
                    counts["completed"] / counts["started"] * 100
                    if counts["started"] > 0
                    else 0
                )
                velocity_data.append(
                    {
                        "interval": day,
                        "started": counts["started"],
                        "completed": counts["completed"],
                        "completion_rate": round(completion_rate, 1),
                    }
                )

        # Calculate trends
        if len(velocity_data) >= 2:
            recent = velocity_data[-2:]
            trend = calculate_trend_indicator(
                recent[1]["started"], recent[0]["started"]
            )
        else:
            trend = "→"

        # Calculate summary statistics
        total_started = sum(d["started"] for d in velocity_data)
        total_completed = sum(d["completed"] for d in velocity_data)
        overall_completion_rate = (
            total_completed / total_started * 100 if total_started > 0 else 0
        )

        response = {
            "period": period,
            "interval": interval,
            "trend": trend,
            "velocity_data": velocity_data,
            "summary": {
                "total_started": total_started,
                "total_completed": total_completed,
                "overall_completion_rate": round(overall_completion_rate, 1),
                "avg_per_interval": round(total_started / len(velocity_data), 2)
                if velocity_data
                else 0,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache the result
        await db.set_analytics_snapshot(user_id, cache_key, response, ttl_seconds=21600)

        return response
    except Exception as e:
        logger.error("Error getting research velocity: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate research velocity: {str(e)}"
        )


@router.get("/journal-themes")
async def get_journal_themes(
    period: str = Query("30d", description="Period: 7d, 30d, 90d, 180d"),
    min_count: int = Query(2, description="Minimum occurrences to qualify as a theme"),
) -> Dict[str, Any]:
    """
    Extract top recurring themes from journal entries.
    Delegates to journal clustering logic for topic extraction.
    """
    try:
        # Parse period
        if not period.endswith("d"):
            raise HTTPException(status_code=400, detail="Period must end with 'd'")

        period_days = int(period[:-1])
        if period_days <= 0:
            raise HTTPException(status_code=400, detail="Period days must be positive")

        # Generate cache key
        cache_key = f"journal-themes:{period}:{min_count}"
        user_id = "user"

        # Check cache
        cached_data = await db.get_analytics_snapshot(user_id, cache_key)
        if cached_data:
            return cached_data

        # Extract journal topics
        topics = await extract_topics_from_journal(period_days)

        # Filter by minimum count
        themes = [t for t in topics if t["count"] >= min_count]

        # Group similar topics (basic stemming/similarity)
        similar_groups: List[Dict[str, Any]] = []
        used_topics = set()

        for topic_data in themes:
            topic = topic_data["topic"]
            if topic in used_topics:
                continue

            # Find similar topics
            similar = []
            for other_data in themes:
                other = other_data["topic"]
                if other == topic or other in used_topics:
                    continue

                # Simple similarity check: contained within or shares words
                if topic in other or other in topic:
                    similar.append(other_data)
                    used_topics.add(other)

            used_topics.add(topic)

            # Calculate total count
            total_count = topic_data["count"] + sum(s["count"] for s in similar)

            similar_groups.append(
                {
                    "primary_topic": topic,
                    "total_count": total_count,
                    "similar_variants": [s["topic"] for s in similar],
                    "examples": [],  # Could add example snippets here
                }
            )

        # Sort by total count
        similar_groups.sort(key=lambda x: x["total_count"], reverse=True)

        response = {
            "period": period,
            "themes": similar_groups[:50],  # Top 50 themes
            "theme_count": len(similar_groups),
            "total_entries_analyzed": len(
                await extract_topics_from_journal(period_days)
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache the result
        await db.set_analytics_snapshot(user_id, cache_key, response, ttl_seconds=21600)

        return response
    except Exception as e:
        logger.error("Error getting journal themes: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to extract journal themes: {str(e)}"
        )


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for analytics service."""
    return {"status": "healthy", "service": "analytics"}


def jaccard_similarity(set1: set, set2: set) -> float:
    """Calculate Jaccard similarity between two sets."""
    if not set1 and not set2:
        return 1.0
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


async def calculate_metric(
    metric: str, period_a_days: int, period_b_days: int
) -> Dict[str, Any]:
    """Calculate specific metric for two periods."""
    # For now, implement simple calculations
    # TODO: Add more sophisticated calculations using actual data

    if metric == "manufacturing_volume":
        # Mock implementation - replace with actual logic
        return {
            "value_a": 100,
            "value_b": 120,
            "delta": 20,
            "delta_pct": 16.7,
            "direction": "up",
            "unit": "count",
        }
    elif metric == "research_capacity":
        # Mock implementation
        return {
            "value_a": 80,
            "value_b": 90,
            "delta": 10,
            "delta_pct": 12.5,
            "direction": "up",
            "unit": "percent",
        }
    elif metric == "production_efficiency":
        # Mock implementation
        return {
            "value_a": 0.75,
            "value_b": 0.82,
            "delta": 0.07,
            "delta_pct": 9.3,
            "direction": "up",
            "unit": "ratio",
        }
    elif metric == "cost_per_unit":
        # Mock implementation
        return {
            "value_a": 15.50,
            "value_b": 14.20,
            "delta": -1.30,
            "delta_pct": -8.4,
            "direction": "down",
            "unit": "currency",
            "is_negative_positive": True,  # Lower is better
        }
    elif metric == "inventory_turnover":
        # Mock implementation
        return {
            "value_a": 8.5,
            "value_b": 11.2,
            "delta": 2.7,
            "delta_pct": 31.8,
            "direction": "up",
            "unit": "ratio",
            "is_negative_positive": True,  # Higher is better
        }
    elif metric == "profitability":
        # Mock implementation
        return {
            "value_a": 0.22,
            "value_b": 0.28,
            "delta": 0.06,
            "delta_pct": 27.3,
            "direction": "up",
            "unit": "ratio",
        }
    elif metric == "topics":
        # For topics, we'll use Jaccard similarity between the two periods
        topics_a = await extract_topics_from_journal(period_a_days)
        topics_b = await extract_topics_from_journal(period_b_days)

        set_a = {t["topic"] for t in topics_a[:30]}  # Top 30 topics
        set_b = {t["topic"] for t in topics_b[:30]}

        similarity = jaccard_similarity(set_a, set_b)

        return {
            "value_a": similarity,
            "value_b": similarity,  # Same value for direct comparison
            "delta": 0,  # Topics similarity is not directional
            "delta_pct": 0,
            "direction": "neutral",
            "unit": "similarity",
            "details": {
                "period_a_topics": list(set_a)[:10],
                "period_b_topics": list(set_b)[:10],
            },
        }
    else:
        raise ValueError(f"Unknown metric: {metric}")


@router.get("/compare")
async def compare_periods(
    metric: str = Query(
        ...,
        description="Metric to compare: manufacturing_volume, research_capacity, production_efficiency, cost_per_unit, inventory_turnover, profitability, topics",
    ),
    period_a_days: int = Query(30, description="Days for period A"),
    period_b_days: int = Query(30, description="Days for period B"),
) -> Dict[str, Any]:
    """
    Compare two time periods for a specific metric with delta calculations and narrative.
    """
    try:
        # Validate metric
        valid_metrics = [
            "manufacturing_volume",
            "research_capacity",
            "production_efficiency",
            "cost_per_unit",
            "inventory_turnover",
            "profitability",
            "topics",
        ]
        if metric not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric. Must be one of: {valid_metrics}",
            )

        # Generate cache key
        cache_key = f"compare:{metric}:{period_a_days}:{period_b_days}"
        user_id = "user"

        # Check cache
        cached_data = await db.get_analytics_snapshot(user_id, cache_key)
        if cached_data:
            return cached_data

        # Calculate metric for both periods
        metric_data = await calculate_metric(metric, period_a_days, period_b_days)

        # Generate human-readable labels
        if metric == "manufacturing_volume":
            label = "Manufacturing Volume"
        elif metric == "research_capacity":
            label = "Research Capacity"
        elif metric == "production_efficiency":
            label = "Production Efficiency"
        elif metric == "cost_per_unit":
            label = "Cost per Unit"
        elif metric == "inventory_turnover":
            label = "Inventory Turnover"
        elif metric == "profitability":
            label = "Profitability"
        else:
            label = metric.capitalize()

        # Build the comparison response
        comparison_data = {
            "metric": metric,
            "metric_label": label,
            "period_a_days": period_a_days,
            "period_b_days": period_b_days,
            "values": {
                "period_a": metric_data["value_a"],
                "period_b": metric_data["value_b"],
            },
            "delta": metric_data["delta"],
            "delta_pct": metric_data["delta_pct"],
            "direction": metric_data["direction"],
            "unit": metric_data["unit"],
            "narrative": "",  # Will be generated below
        }

        # Handle special case for metrics where lower values are better
        if (
            "is_negative_positive" in metric_data
            and metric_data["is_negative_positive"]
        ):
            # For metrics where downward is positive (e.g., cost per unit)
            if metric_data["direction"] == "down":
                comparison_data["interpretation"] = "positive"
                if "unit" in metric_data and metric_data["unit"] == "currency":
                    interpretation_text = (
                        f"decreased by ${abs(metric_data['delta']):.2f}"
                    )
                else:
                    interpretation_text = (
                        f"decreased by {abs(metric_data['delta_pct']):.1f}%"
                    )
            elif metric_data["direction"] == "up":
                comparison_data["interpretation"] = "negative"
                if "unit" in metric_data and metric_data["unit"] == "currency":
                    interpretation_text = f"increased by ${metric_data['delta']:.2f}"
                else:
                    interpretation_text = (
                        f"increased by {metric_data['delta_pct']:.1f}%"
                    )
            else:
                comparison_data["interpretation"] = "neutral"
                interpretation_text = "remained stable"
        else:
            # For normal metrics, upward is positive
            if metric_data["direction"] == "up":
                comparison_data["interpretation"] = "positive"
                interpretation_text = f"increased by {metric_data['delta_pct']:.1f}%"
            elif metric_data["direction"] == "down":
                comparison_data["interpretation"] = "negative"
                interpretation_text = (
                    f"decreased by {abs(metric_data['delta_pct']):.1f}%"
                )
            else:
                comparison_data["interpretation"] = "neutral"
                interpretation_text = "remained stable"

        comparison_data["interpretation_text"] = interpretation_text

        # Generate narrative using the interpretation
        narrative = f"{label} from {period_a_days} days to {period_b_days} days: from {metric_data['value_a']} ({period_a_days}d) to {metric_data['value_b']} ({period_b_days}d): {interpretation_text}"
        comparison_data["narrative"] = narrative

        # Add extra details for topics metric
        if metric == "topics" and "details" in metric_data:
            comparison_data["topics_similarity"] = metric_data["value_a"]
            comparison_data["shared_topic_percentage"] = (
                f"{metric_data['value_a'] * 100:.1f}%"
            )
            comparison_data["period_a_top_topics"] = metric_data["details"][
                "period_a_topics"
            ]
            comparison_data["period_b_top_topics"] = metric_data["details"][
                "period_b_topics"
            ]

            if metric_data["value_a"] >= 0.7:
                similarity_level = "high"
            elif metric_data["value_a"] >= 0.4:
                similarity_level = "moderate"
            else:
                similarity_level = "low"

            comparison_data["similarity_level"] = similarity_level
            comparison_data["narrative"] = (
                f"Topic similarity from {period_a_days} days to {period_b_days} days: {similarity_level} ({metric_data['value_a'] * 100:.1f}%). {period_a_days}d: {', '.join(metric_data['details']['period_a_topics'][:5])}. {period_b_days}d: {', '.join(metric_data['details']['period_b_topics'][:5])}"
            )

        # Cache the result
        await db.set_analytics_snapshot(
            user_id, cache_key, comparison_data, ttl_seconds=21600
        )

        return comparison_data
    except Exception as e:
        logger.error("Error comparing periods: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to compare periods: {str(e)}"
        )


@router.get("/comparison-preview")
async def comparison_preview() -> Dict[str, List[Dict[str, Any]]]:
    """
    Preview available metrics for comparison and example results.
    """
    preview_data = [
        {
            "metric": "manufacturing_volume",
            "label": "Manufacturing Volume",
            "units": "count",
            "period_suggestion": "Compare two production periods by day or week",
        },
        {
            "metric": "research_capacity",
            "label": "Research Capacity",
            "units": "percent",
            "period_suggestion": "Compare resource allocation and utilisation",
        },
        {
            "metric": "production_efficiency",
            "label": "Production Efficiency",
            "units": "ratio",
            "period_suggestion": "Compare output-to-input ratios",
        },
        {
            "metric": "cost_per_unit",
            "label": "Cost per Unit",
            "units": "currency",
            "period_suggestion": "Track cost reduction trends (note: downward metric is positive)",
        },
        {
            "metric": "inventory_turnover",
            "label": "Inventory Turnover",
            "units": "ratio",
            "period_suggestion": "Compare inventory velocity (higher = better)",
        },
        {
            "metric": "profitability",
            "label": "Profitability",
            "units": "ratio",
            "period_suggestion": "Compare profit margins between periods",
        },
        {
            "metric": "topics",
            "label": "Topic Similarity",
            "units": "similarity score",
            "period_suggestion": "Compare journal topic overlap with Jaccard similarity",
        },
    ]

    return {"available_metrics": preview_data}
