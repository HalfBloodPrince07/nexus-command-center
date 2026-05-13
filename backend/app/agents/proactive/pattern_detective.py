"""
PatternDetective -- proactive agent that scans journal / mood / memory data
for streaks, correlations, anomalies, and frequency spikes, then persists
any discoveries as Insight rows.

Runs on a schedule (nightly or periodic) or on-demand via the supervisor.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean, stdev
from typing import Any

from backend.config import settings
from backend.core.database import (
    create_insight,
    get_memory_records,
    get_mood_series,
    list_insights,
    list_journal_entries,
)

logger = logging.getLogger(__name__)

# ── Settings shortcuts ──────────────────────────────────────────────────────
_Z_THRESHOLD: float = settings.ANOMALY_Z_THRESHOLD          # default 2.0
_MIN_SEVERITY: float = settings.INSIGHT_MIN_SEVERITY         # default 0.4
_WINDOWS: list[int] = list(settings.PATTERN_WINDOWS_DAYS)    # [7, 30, 90]
_DEDUP_WINDOW_DAYS: int = 7  # look-back for title-based dedup


class PatternDetective:
    """Scans multi-day windows for behavioural patterns and stores insights."""

    # ------------------------------------------------------------------
    # Public entry-points
    # ------------------------------------------------------------------

    async def run_full_scan(self) -> list[dict[str, Any]]:
        """Run every detection method across the configured time windows.

        Returns a list of insight dicts that were created during this scan.
        """
        created: list[dict[str, Any]] = []

        # Use the two shortest windows (typically 7d and 30d) as requested
        windows = _WINDOWS[:2] if len(_WINDOWS) >= 2 else _WINDOWS

        for window in windows:
            try:
                mood_data = await get_mood_series(window)
            except Exception:
                logger.exception("Failed to fetch mood series for %d-day window", window)
                mood_data = []

            # --- streaks ---
            try:
                streak_insights = await self.detect_streaks(mood_data, min_length=3)
                for ins in streak_insights:
                    saved = await self._maybe_save(ins, window)
                    if saved:
                        created.append(saved)
            except Exception:
                logger.exception("Streak detection failed (window=%d)", window)

            # --- mood anomalies ---
            try:
                anomaly_insights = await self._detect_mood_anomalies(mood_data)
                for ins in anomaly_insights:
                    saved = await self._maybe_save(ins, window)
                    if saved:
                        created.append(saved)
            except Exception:
                logger.exception("Anomaly detection failed (window=%d)", window)

        # --- correlations (window-independent, uses full 30d) ---
        try:
            corr_insights = await self.detect_correlations()
            for ins in corr_insights:
                saved = await self._maybe_save(ins, window=30)
                if saved:
                    created.append(saved)
        except Exception:
            logger.exception("Correlation detection failed")

        # --- frequency spikes (always 7d) ---
        try:
            spike_insights = await self.detect_frequency_spikes()
            for ins in spike_insights:
                saved = await self._maybe_save(ins, window=7)
                if saved:
                    created.append(saved)
        except Exception:
            logger.exception("Frequency spike detection failed")

        logger.info("PatternDetective full scan complete -- %d new insights", len(created))
        return created

    async def anomaly_scan(self) -> list[dict[str, Any]]:
        """Lightweight scan: mood anomalies + frequency spikes only."""
        created: list[dict[str, Any]] = []

        try:
            mood_data = await get_mood_series(7)
        except Exception:
            logger.exception("Failed to fetch mood series for anomaly scan")
            mood_data = []

        try:
            for ins in await self._detect_mood_anomalies(mood_data):
                saved = await self._maybe_save(ins, window=7)
                if saved:
                    created.append(saved)
        except Exception:
            logger.exception("Mood anomaly detection failed in anomaly_scan")

        try:
            for ins in await self.detect_frequency_spikes():
                saved = await self._maybe_save(ins, window=7)
                if saved:
                    created.append(saved)
        except Exception:
            logger.exception("Frequency spike detection failed in anomaly_scan")

        logger.info("PatternDetective anomaly scan complete -- %d new insights", len(created))
        return created

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    async def detect_streaks(
        self,
        metric_data: list[dict[str, Any]],
        min_length: int = 3,
    ) -> list[dict[str, Any]]:
        """Find N consecutive days of the same trend direction in *metric_data*.

        Each element must have at least ``score`` (numeric) and ``date``.
        Returns raw insight dicts (not yet persisted).
        """
        if len(metric_data) < 2:
            return []

        insights: list[dict[str, Any]] = []
        direction: str | None = None  # "up" or "down"
        streak_start = 0

        for i in range(1, len(metric_data)):
            prev_score = metric_data[i - 1].get("score", 0)
            curr_score = metric_data[i].get("score", 0)

            if curr_score > prev_score:
                new_dir = "up"
            elif curr_score < prev_score:
                new_dir = "down"
            else:
                new_dir = direction  # tie continues current streak

            if new_dir != direction:
                # streak broken -- check if the just-ended one was long enough
                streak_len = i - streak_start
                if direction is not None and streak_len >= min_length:
                    insights.append(self._streak_to_insight(
                        metric_data, streak_start, i - 1, direction, streak_len,
                    ))
                direction = new_dir
                streak_start = i

        # handle trailing streak
        streak_len = len(metric_data) - streak_start
        if direction is not None and streak_len >= min_length:
            insights.append(self._streak_to_insight(
                metric_data, streak_start, len(metric_data) - 1, direction, streak_len,
            ))

        return insights

    async def detect_correlations(self) -> list[dict[str, Any]]:
        """Check correlation between mood scores and interaction sentiment.

        Uses the full 30-day window.  Returns raw insight dicts.
        """
        insights: list[dict[str, Any]] = []

        try:
            mood_data = await get_mood_series(30)
            entries = await list_journal_entries(limit=200)
            memory_recs = await get_memory_records(limit=200, category="interaction")
        except Exception:
            logger.exception("Failed to gather data for correlation detection")
            return []

        if len(mood_data) < 5 or len(memory_recs) < 5:
            return []

        # Build date -> mood score map
        mood_by_date: dict[str, float] = {}
        for m in mood_data:
            dt = m.get("date")
            if dt is None:
                continue
            key = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
            mood_by_date[key] = float(m.get("score", 0))

        # Build date -> average sentiment map from memory records
        sentiment_by_date: dict[str, list[float]] = {}
        for rec in memory_recs:
            dt = rec.get("created_at")
            if dt is None:
                continue
            key = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
            # Try to extract sentiment from content (best-effort JSON parse)
            content = rec.get("content", "")
            sentiment = self._extract_sentiment(content)
            if sentiment is not None:
                sentiment_by_date.setdefault(key, []).append(sentiment)

        # Align the two series by date
        aligned_mood: list[float] = []
        aligned_sent: list[float] = []
        for date_key in sorted(mood_by_date.keys()):
            if date_key in sentiment_by_date:
                aligned_mood.append(mood_by_date[date_key])
                aligned_sent.append(mean(sentiment_by_date[date_key]))

        if len(aligned_mood) < 5:
            return []

        corr = self._pearson(aligned_mood, aligned_sent)
        if corr is None:
            return []

        abs_corr = abs(corr)
        if abs_corr >= 0.6:
            direction = "positive" if corr > 0 else "negative"
            severity = min(1.0, 0.4 + abs_corr * 0.5)
            insights.append({
                "category": "correlation",
                "severity": round(severity, 2),
                "title": f"Mood-sentiment {direction} correlation detected (r={corr:+.2f})",
                "body_md": (
                    f"Over the last 30 days your mood scores show a **{direction}** "
                    f"correlation (r={corr:+.2f}) with the average sentiment of your "
                    f"logged interactions.  This was computed from {len(aligned_mood)} "
                    f"matched data points."
                ),
            })

        return insights

    async def detect_frequency_spikes(self) -> list[dict[str, Any]]:
        """Topics or people that jumped from 0-1 mentions to >=3 in the last 7 days."""
        insights: list[dict[str, Any]] = []

        try:
            recent_entries = await list_journal_entries(limit=100)
            recent_memories = await get_memory_records(limit=200, category=None)
        except Exception:
            logger.exception("Failed to gather data for frequency spike detection")
            return []

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        recent_words: list[str] = []
        baseline_words: list[str] = []

        for entry in recent_entries:
            created = entry.get("created_at")
            if created is None:
                continue
            if not isinstance(created, datetime):
                continue
            body = entry.get("body_md", "") or ""
            words = self._extract_notable_tokens(body)
            if created >= seven_days_ago:
                recent_words.extend(words)
            elif created >= thirty_days_ago:
                baseline_words.extend(words)

        for mem in recent_memories:
            created = mem.get("created_at")
            if created is None:
                continue
            if not isinstance(created, datetime):
                continue
            content = mem.get("content", "") or ""
            words = self._extract_notable_tokens(content)
            if created >= seven_days_ago:
                recent_words.extend(words)
            elif created >= thirty_days_ago:
                baseline_words.extend(words)

        recent_counts = Counter(recent_words)
        baseline_counts = Counter(baseline_words)

        for token, recent_count in recent_counts.items():
            baseline_count = baseline_counts.get(token, 0)
            if baseline_count <= 1 and recent_count >= 3:
                severity = min(1.0, 0.4 + 0.1 * recent_count)
                insights.append({
                    "category": "frequency_spike",
                    "severity": round(severity, 2),
                    "title": f"Spike in mentions: \"{token}\"",
                    "body_md": (
                        f"The term **\"{token}\"** appeared **{recent_count}** times "
                        f"in the last 7 days, up from only **{baseline_count}** in the "
                        f"prior 23 days.  This could signal a new focus area or concern."
                    ),
                })

        return insights

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _detect_mood_anomalies(
        self,
        mood_data: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Flag individual mood scores that deviate by more than Z_THRESHOLD
        standard deviations from the window mean."""
        if len(mood_data) < 3:
            return []

        scores = [float(m.get("score", 0)) for m in mood_data]
        mu = mean(scores)
        try:
            sigma = stdev(scores)
        except Exception:
            return []

        if sigma == 0:
            return []

        insights: list[dict[str, Any]] = []
        for m in mood_data:
            score = float(m.get("score", 0))
            z = (score - mu) / sigma
            if abs(z) >= _Z_THRESHOLD:
                direction = "high" if z > 0 else "low"
                dt = m.get("date")
                date_str = (
                    dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)[:10]
                )
                severity = min(1.0, _MIN_SEVERITY + abs(z) * 0.15)
                insights.append({
                    "category": "mood_anomaly",
                    "severity": round(severity, 2),
                    "title": f"Unusual mood ({direction}) on {date_str}",
                    "body_md": (
                        f"Your mood score of **{score}** on {date_str} is "
                        f"**{abs(z):.1f} standard deviations** {direction}er than "
                        f"the period average of {mu:.1f} (sigma={sigma:.2f})."
                    ),
                })

        return insights

    def _streak_to_insight(
        self,
        data: list[dict[str, Any]],
        start_idx: int,
        end_idx: int,
        direction: str,
        length: int,
    ) -> dict[str, Any]:
        start_score = data[start_idx].get("score", "?")
        end_score = data[end_idx].get("score", "?")
        start_dt = data[start_idx].get("date")
        end_dt = data[end_idx].get("date")
        start_str = (
            start_dt.strftime("%Y-%m-%d") if isinstance(start_dt, datetime) else str(start_dt)[:10]
        )
        end_str = (
            end_dt.strftime("%Y-%m-%d") if isinstance(end_dt, datetime) else str(end_dt)[:10]
        )
        severity = min(1.0, _MIN_SEVERITY + 0.1 * length)
        return {
            "category": "streak",
            "severity": round(severity, 2),
            "title": f"{length}-day {direction}ward mood streak ({start_str} to {end_str})",
            "body_md": (
                f"Your mood has been trending **{direction}** for "
                f"**{length} consecutive days** ({start_str} - {end_str}), "
                f"moving from {start_score} to {end_score}."
            ),
        }

    async def _maybe_save(
        self,
        insight_dict: dict[str, Any],
        window: int,
    ) -> dict[str, Any] | None:
        """Deduplicate and persist an insight, returning the saved dict or None."""
        title = insight_dict.get("title", "")
        severity = insight_dict.get("severity", 0.0)

        # Severity gate
        if severity < _MIN_SEVERITY:
            return None

        # Dedup: same title in the last N days
        try:
            recent = await list_insights(limit=50)
        except Exception:
            logger.exception("Could not fetch existing insights for dedup")
            recent = []

        cutoff = datetime.now(timezone.utc) - timedelta(days=_DEDUP_WINDOW_DAYS)
        for existing in recent:
            if existing.get("title") == title:
                created = existing.get("created_at")
                if isinstance(created, datetime) and created >= cutoff:
                    logger.debug("Skipping duplicate insight: %s", title)
                    return None

        insight_id = str(uuid.uuid4())
        try:
            await create_insight(
                id=insight_id,
                category=insight_dict.get("category", "general"),
                severity=severity,
                title=title,
                body_md=insight_dict.get("body_md", ""),
            )
        except Exception:
            logger.exception("Failed to persist insight: %s", title)
            return None

        saved = {**insight_dict, "id": insight_id, "window_days": window}
        logger.info("Created insight [%s]: %s (severity=%.2f)", insight_id[:8], title, severity)
        return saved

    # ------------------------------------------------------------------
    # Pure helpers (no I/O)
    # ------------------------------------------------------------------

    @staticmethod
    def _pearson(xs: list[float], ys: list[float]) -> float | None:
        """Compute Pearson r between two equal-length lists. Returns None on error."""
        n = len(xs)
        if n < 3 or n != len(ys):
            return None
        try:
            mx, my = mean(xs), mean(ys)
            sx, sy = stdev(xs), stdev(ys)
            if sx == 0 or sy == 0:
                return None
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
            return cov / (sx * sy)
        except Exception:
            return None

    @staticmethod
    def _extract_sentiment(content: str) -> float | None:
        """Best-effort extraction of a numeric sentiment from a memory record's
        content string.  Returns None when nothing useful can be parsed."""
        import json as _json

        try:
            data = _json.loads(content)
            if isinstance(data, dict):
                for key in ("sentiment", "score", "mood"):
                    val = data.get(key)
                    if val is not None:
                        return float(val)
        except (ValueError, TypeError):
            pass
        return None

    @staticmethod
    def _extract_notable_tokens(text: str) -> list[str]:
        """Rough tokeniser: lowercased words >= 4 chars, stripped of punctuation.

        Excludes an intentionally small stop-list so that domain-specific terms
        (people's names, project names, etc.) surface as spikes.
        """
        import re

        _STOP = frozenset({
            "this", "that", "with", "from", "they", "them", "their", "been",
            "have", "were", "will", "would", "could", "should", "about",
            "just", "more", "some", "than", "very", "also", "into", "over",
            "only", "then", "when", "what", "which", "there", "these", "your",
            "like", "make", "know", "time", "well", "back", "after", "think",
            "does", "much", "even", "most", "made", "each", "still", "every",
            "really", "because", "through", "going", "where", "being",
        })
        tokens = re.findall(r"[a-z]{4,}", text.lower())
        return [t for t in tokens if t not in _STOP]
