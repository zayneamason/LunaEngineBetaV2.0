"""
Runtime Watchdog
================

Monitors Luna's critical systems during runtime.
Logs warnings if systems degrade during operation.

The watchdog runs in the background and periodically checks:
- LoRA adapter still exists
- Memory database is accessible
- Local inference is still loaded
- Memory integrity (node count)
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, List
import sqlite3

logger = logging.getLogger(__name__)


class WatchdogAlert:
    """Represents a watchdog alert."""

    def __init__(self, level: str, system: str, message: str):
        self.level = level  # "warning" or "critical"
        self.system = system
        self.message = message

    def __repr__(self):
        return f"WatchdogAlert({self.level}: {self.system} - {self.message})"


class LunaWatchdog:
    """
    Monitors Luna's critical systems during runtime.

    Runs periodic health checks and emits alerts if systems degrade.
    """

    def __init__(
        self,
        check_interval: int = 60,
        project_root: Optional[Path] = None,
        alert_callback: Optional[Callable[[WatchdogAlert], None]] = None,
        engine: Optional[object] = None,
    ):
        """
        Initialize the watchdog.

        Args:
            check_interval: Seconds between health checks (default: 60)
            project_root: Root directory of Luna project
            alert_callback: Optional callback for alerts (default: log only)
            engine: Optional LunaEngine reference for pipeline checks
        """
        self.check_interval = check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._engine = engine
        self._start_time: Optional[float] = None

        if project_root is None:
            self.project_root = Path(__file__).parent.parent.parent.parent
        else:
            self.project_root = Path(project_root)

        self._alert_callback = alert_callback

        # Track consecutive failures for escalation
        self._failure_counts = {}

        # Minimum expected values (lowered after brain scrub Jan 2026)
        self.min_memory_nodes = 10000
        self.min_graph_edges = 10000

    def _emit_alert(self, alert: WatchdogAlert):
        """Emit an alert via logging and optional callback."""
        if alert.level == "critical":
            logger.critical(f"🚨 WATCHDOG: {alert.system} - {alert.message}")
        else:
            logger.warning(f"⚠️ WATCHDOG: {alert.system} - {alert.message}")

        if self._alert_callback:
            try:
                self._alert_callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def _check_lora_adapter(self) -> Optional[WatchdogAlert]:
        """Check if LoRA adapter still exists."""
        lora_path = self.project_root / "models/luna_lora_mlx/adapters.safetensors"

        if not lora_path.exists():
            return WatchdogAlert(
                "critical",
                "LoRA Adapter",
                f"LoRA adapter missing at {lora_path}!"
            )

        # Check file size (should be ~114MB)
        size = lora_path.stat().st_size
        if size < 100_000_000:  # Less than 100MB is suspicious
            return WatchdogAlert(
                "warning",
                "LoRA Adapter",
                f"LoRA adapter seems corrupted ({size} bytes, expected ~114MB)"
            )

        return None

    def _check_memory_database(self) -> Optional[WatchdogAlert]:
        """Check memory database is accessible and has data."""
        db_path = self.project_root / "data/luna_engine.db"

        if not db_path.exists():
            return WatchdogAlert(
                "critical",
                "Memory Database",
                "Memory database missing!"
            )

        try:
            conn = sqlite3.connect(str(db_path))

            # Check node count
            nodes = conn.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
            edges = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
            conn.close()

            if nodes < self.min_memory_nodes:
                return WatchdogAlert(
                    "critical",
                    "Memory Integrity",
                    f"Memory degradation! Only {nodes} nodes (expected >{self.min_memory_nodes})"
                )

            if edges < self.min_graph_edges:
                return WatchdogAlert(
                    "warning",
                    "Memory Integrity",
                    f"Edge loss detected! Only {edges} edges (expected >{self.min_graph_edges})"
                )

        except Exception as e:
            return WatchdogAlert(
                "critical",
                "Memory Database",
                f"Database error: {e}"
            )

        return None

    def _check_local_inference(self) -> Optional[WatchdogAlert]:
        """Check if local inference is still importable."""
        try:
            from luna.inference import LocalInference
            return None
        except ImportError as e:
            return WatchdogAlert(
                "critical",
                "Local Inference",
                f"Local inference broken: {e}"
            )

    def _check_extraction_pipeline(self) -> Optional[WatchdogAlert]:
        """
        Check if the extraction pipeline is actually firing.

        Only alerts after Luna has been running for 5+ minutes AND
        has processed messages — avoids false alarms on idle instances.
        """
        if not self._engine:
            return None

        import time
        if self._start_time is None:
            return None

        uptime_minutes = (time.monotonic() - self._start_time) / 60
        if uptime_minutes < 5:
            return None  # Too early to judge

        messages_processed = getattr(self._engine.metrics, "messages_generated", 0)
        if messages_processed < 3:
            return None  # Not enough traffic to judge

        scribe = self._engine.get_actor("scribe")
        if not scribe:
            return WatchdogAlert(
                "critical",
                "Extraction Pipeline",
                "Scribe actor not registered — extraction pipeline is offline"
            )

        stats = scribe.get_stats()
        extractions = stats.get("extractions_count", 0)

        if extractions == 0:
            return WatchdogAlert(
                "warning",
                "Extraction Pipeline",
                f"0 extractions after {messages_processed} messages processed. "
                f"Pipeline may be disconnected."
            )

        librarian = self._engine.get_actor("librarian")
        if librarian:
            lib_stats = librarian.get_stats()
            filings = lib_stats.get("filings_count", 0)
            if filings == 0 and extractions > 0:
                return WatchdogAlert(
                    "warning",
                    "Extraction Pipeline",
                    f"Scribe has {extractions} extractions but Librarian has 0 filings. "
                    f"Scribe → Librarian link may be broken."
                )

        return None

    async def _run_checks(self) -> List[WatchdogAlert]:
        """Run all health checks and return any alerts."""
        alerts = []

        # Run checks (synchronous, but we're in async context)
        for check_name, check_func in [
            ("lora", self._check_lora_adapter),
            ("memory", self._check_memory_database),
            ("inference", self._check_local_inference),
            ("extraction", self._check_extraction_pipeline),
        ]:
            try:
                alert = check_func()
                if alert:
                    # Track consecutive failures
                    self._failure_counts[check_name] = self._failure_counts.get(check_name, 0) + 1

                    # Escalate to critical after 3 consecutive failures
                    if self._failure_counts[check_name] >= 3 and alert.level == "warning":
                        alert.level = "critical"
                        alert.message += " (escalated after 3 consecutive failures)"

                    alerts.append(alert)
                else:
                    # Reset failure count on success
                    self._failure_counts[check_name] = 0

            except Exception as e:
                alerts.append(WatchdogAlert(
                    "warning",
                    check_name,
                    f"Check itself failed: {e}"
                ))

        return alerts

    async def check_once(self) -> List[WatchdogAlert]:
        """Run a single health check cycle (for testing)."""
        return await self._run_checks()

    async def start(self):
        """Start the watchdog loop."""
        if self._running:
            logger.warning("Watchdog already running")
            return

        import time
        self._running = True
        self._start_time = time.monotonic()
        logger.info(f"Watchdog starting (interval: {self.check_interval}s)")

        while self._running:
            try:
                alerts = await self._run_checks()

                for alert in alerts:
                    self._emit_alert(alert)

                if not alerts:
                    logger.debug("Watchdog: All systems healthy")

            except Exception as e:
                logger.error(f"Watchdog check cycle failed: {e}")

            await asyncio.sleep(self.check_interval)

    def stop(self):
        """Stop the watchdog loop."""
        self._running = False
        logger.info("Watchdog stopped")

    async def start_background(self) -> asyncio.Task:
        """Start watchdog as a background task."""
        self._task = asyncio.create_task(self.start())
        return self._task


# Global watchdog instance
_watchdog: Optional[LunaWatchdog] = None


def get_watchdog(
    check_interval: int = 60,
    project_root: Optional[Path] = None,
    engine: Optional[object] = None,
) -> LunaWatchdog:
    """Get or create the global watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = LunaWatchdog(check_interval, project_root, engine=engine)
    elif engine is not None and _watchdog._engine is None:
        _watchdog._engine = engine
    return _watchdog


async def start_watchdog(check_interval: int = 60, engine: Optional[object] = None) -> asyncio.Task:
    """Start the global watchdog in the background."""
    watchdog = get_watchdog(check_interval, engine=engine)
    return await watchdog.start_background()


if __name__ == "__main__":
    # Allow running as standalone test
    import asyncio

    async def main():
        watchdog = LunaWatchdog(check_interval=5)
        alerts = await watchdog.check_once()

        print("Watchdog Single Check Results:")
        print("=" * 60)

        if alerts:
            for alert in alerts:
                print(f"  {alert}")
        else:
            print("  ✅ All systems healthy")

        print("=" * 60)

    asyncio.run(main())
