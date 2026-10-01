"""System diagnostics, metrics tracking, quota caching, and environment sanitization."""

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import time
from datetime import UTC, datetime
from typing import Any

from karaagy import __version__ as karaagy_version
from karaagy.config import settings

logger = logging.getLogger(__name__)

# Sensitive variable name substrings that must be masked
SENSITIVE_KEYWORDS = (
    "KEY",
    "TOKEN",
    "SECRET",
    "AUTH",
    "PASSWORD",
    "PASSWD",
    "CREDENTIAL",
    "PRIVATE",
    "COOKIE",
)

# Known non-sensitive configuration keys that should never be redacted
EXPLICIT_SAFE_KEYS = {
    "KARAAGY_ENABLE_AUTO_PRUNE_SESSIONS",
    "KARAAGY_MAX_CONCURRENT_SESSIONS",
    "KARAAGY_DEFAULT_MODEL",
    "KARAAGY_DEFAULT_EFFORT",
    "KARAAGY_HOST",
    "KARAAGY_PORT",
    "KARAAGY_CACHE_TTL_SECONDS",
    "KARAAGY_USAGE_CACHE_TTL_SECONDS",
    "KARAAGY_IMAGE_CACHE_TTL_SECONDS",
    "KARAAGY_IMAGE_CACHE_DIR",
    "KARAAGY_MAX_RETRIES",
    "KARAAGY_INITIAL_BACKOFF",
}


class DiagnosticsManager:
    """Manages system metrics, Antigravity usage quota caching, and environment diagnostics."""

    _start_time: float = time.time()
    _total_requests: int = 0
    _successful_requests: int = 0
    _failed_requests: int = 0
    _total_prompt_tokens: int = 0
    _total_completion_tokens: int = 0

    _cached_agy_version: str | None = None
    _cached_git_commit: str | None = None

    _cached_usage: dict[str, Any] | None = None
    _usage_last_fetched_at: float = 0.0
    _usage_lock: asyncio.Lock | None = None

    @classmethod
    def _get_usage_lock(cls) -> asyncio.Lock:
        if cls._usage_lock is None:
            cls._usage_lock = asyncio.Lock()
        return cls._usage_lock

    @classmethod
    def record_request_completion(
        cls,
        success: bool,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record a completed completion request for gateway statistics."""
        cls._total_requests += 1
        if success:
            cls._successful_requests += 1
        else:
            cls._failed_requests += 1
        cls._total_prompt_tokens += prompt_tokens
        cls._total_completion_tokens += completion_tokens

    @classmethod
    def get_uptime_seconds(cls) -> float:
        """Return server uptime in seconds."""
        return time.time() - cls._start_time

    @classmethod
    def format_duration(cls, seconds: float) -> str:
        """Format seconds into a human-readable duration string (e.g. '2d 4h 12m' or '45m 10s')."""
        s = int(seconds)
        days, remainder = divmod(s, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    @classmethod
    def get_gateway_metrics(cls) -> dict[str, Any]:
        """Return cumulative gateway throughput metrics."""
        uptime = cls.get_uptime_seconds()
        from karaagy.core.process import get_concurrency_semaphore

        sem = get_concurrency_semaphore()
        active_concurrency = 0
        max_concurrency = settings.max_concurrent_sessions
        if sem is not None:
            # Value indicates available slots; active = max - available
            available = getattr(sem, "_value", max_concurrency)
            active_concurrency = max(0, max_concurrency - available)

        return {
            "uptime_seconds": round(uptime, 2),
            "uptime_formatted": cls.format_duration(uptime),
            "total_requests": cls._total_requests,
            "successful_requests": cls._successful_requests,
            "failed_requests": cls._failed_requests,
            "total_prompt_tokens": cls._total_prompt_tokens,
            "total_completion_tokens": cls._total_completion_tokens,
            "total_tokens": cls._total_prompt_tokens + cls._total_completion_tokens,
            "active_concurrency": active_concurrency,
            "max_concurrency": max_concurrency,
        }

    @classmethod
    def get_git_commit(cls) -> str | None:
        """Retrieve git commit short hash if running inside a git repository or via env."""
        if cls._cached_git_commit is not None:
            return cls._cached_git_commit

        env_commit = os.environ.get("KARAAGY_GIT_COMMIT") or os.environ.get("GIT_COMMIT")
        if env_commit:
            cls._cached_git_commit = env_commit[:7]
            return cls._cached_git_commit

        try:
            git_bin = shutil.which("git")
            if git_bin:
                proc = subprocess.run(
                    [git_bin, "rev-parse", "--short", "HEAD"],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                    check=False,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    cls._cached_git_commit = proc.stdout.strip()
                    return cls._cached_git_commit
        except Exception:
            pass

        cls._cached_git_commit = "release"
        return cls._cached_git_commit

    @classmethod
    def get_karaagy_version_info(cls) -> dict[str, str]:
        """Return Karaagy version and build details."""
        commit = cls.get_git_commit()
        version_str = f"v{karaagy_version}"
        if commit and commit != "release":
            version_str += f" ({commit})"
        return {
            "version": karaagy_version,
            "commit": commit or "unknown",
            "display": version_str,
            "python_version": platform.python_version(),
            "os_platform": f"{platform.system()} {platform.machine()}",
        }

    @classmethod
    def get_agy_version(cls) -> str:
        """Fetch and cache the `agy --version` string."""
        if cls._cached_agy_version is not None:
            return cls._cached_agy_version

        agy_bin = settings.resolve_agy_bin()
        try:
            proc = subprocess.run(
                [agy_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            out = proc.stdout.strip() or proc.stderr.strip()
            if out:
                cls._cached_agy_version = out
                return cls._cached_agy_version
        except Exception as e:
            logger.warning("Failed to determine agy version: %s", e)

        cls._cached_agy_version = "unknown"
        return cls._cached_agy_version

    @classmethod
    async def get_account_quota(cls, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch Antigravity `/usage` quota buckets with TTL caching."""
        now = time.time()
        ttl = settings.usage_cache_ttl_seconds

        if (
            not force_refresh
            and cls._cached_usage is not None
            and (now - cls._usage_last_fetched_at) < ttl
        ):
            age = int(now - cls._usage_last_fetched_at)
            cls._cached_usage["cache_age_seconds"] = age
            cls._cached_usage["cache_age_formatted"] = cls.format_duration(age)
            return cls._cached_usage

        lock = cls._get_usage_lock()
        async with lock:
            # Re-check after acquiring lock
            now = time.time()
            if (
                not force_refresh
                and cls._cached_usage is not None
                and (now - cls._usage_last_fetched_at) < ttl
            ):
                age = int(now - cls._usage_last_fetched_at)
                cls._cached_usage["cache_age_seconds"] = age
                cls._cached_usage["cache_age_formatted"] = cls.format_duration(age)
                return cls._cached_usage

            agy_bin = settings.resolve_agy_bin()
            cmd = [
                agy_bin,
                "-p",
                "/usage",
                "--output-format",
                "json",
                "--dangerously-skip-permissions",
            ]

            try:
                logger.info("Fetching fresh Antigravity quota via `agy -p /usage`")
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
                raw_stdout = stdout.decode("utf-8", errors="replace").strip()

                if proc.returncode == 0 and raw_stdout:
                    data = json.loads(raw_stdout)
                    cmd_data = data.get("command", {}).get("data", {})
                    groups_raw = cmd_data.get("groups", [])

                    parsed_groups = []
                    for group in groups_raw:
                        g_name = group.get("name", "Unknown Group")
                        g_desc = group.get("description", "")
                        buckets = []
                        for b in group.get("buckets", []):
                            remaining_frac = float(b.get("remaining_fraction", 0.0))
                            remaining_pct = round(remaining_frac * 100, 1)
                            reset_time_str = b.get("reset_time", "")
                            buckets.append(
                                {
                                    "id": b.get("id", ""),
                                    "name": b.get("name", ""),
                                    "description": b.get("description", ""),
                                    "window": b.get("window", ""),
                                    "remaining_fraction": remaining_frac,
                                    "remaining_percent": remaining_pct,
                                    "reset_time": reset_time_str,
                                }
                            )
                        parsed_groups.append(
                            {
                                "name": g_name,
                                "description": g_desc,
                                "buckets": buckets,
                            }
                        )

                    cls._cached_usage = {
                        "available": True,
                        "last_fetched_at": datetime.now(UTC).isoformat(),
                        "cache_age_seconds": 0,
                        "cache_age_formatted": "just now",
                        "description": cmd_data.get("description", ""),
                        "groups": parsed_groups,
                        "error": None,
                    }
                    cls._usage_last_fetched_at = now
                    return cls._cached_usage

                err_text = stderr.decode("utf-8", errors="replace").strip() or raw_stdout
                logger.warning("Antigravity /usage command failed: %s", err_text)
                return {
                    "available": False,
                    "last_fetched_at": datetime.now(UTC).isoformat(),
                    "cache_age_seconds": 0,
                    "cache_age_formatted": "never",
                    "description": "",
                    "groups": [],
                    "error": f"CLI exited with code {proc.returncode}: {err_text[:200]}",
                }

            except Exception as e:
                logger.warning("Exception querying Antigravity /usage: %s", e)
                return {
                    "available": False,
                    "last_fetched_at": datetime.now(UTC).isoformat(),
                    "cache_age_seconds": 0,
                    "cache_age_formatted": "never",
                    "description": "",
                    "groups": [],
                    "error": str(e),
                }

    @classmethod
    def is_sensitive_key(cls, key: str) -> bool:
        """Check if environment variable name contains sensitive secret keywords."""
        if key in EXPLICIT_SAFE_KEYS:
            return False
        key_upper = key.upper()
        return any(kw in key_upper for kw in SENSITIVE_KEYWORDS)

    @classmethod
    def get_sanitized_environment(cls) -> dict[str, str]:
        """Return active OS environment variables with sensitive secrets fully masked."""
        sanitized: dict[str, str] = {}
        for k, v in sorted(os.environ.items()):
            if cls.is_sensitive_key(k):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    @classmethod
    def get_runtime_settings_dict(cls) -> dict[str, Any]:
        """Return active Karaagy settings with sensitive fields masked."""
        return {
            "app_name": settings.app_name,
            "host": settings.host,
            "port": settings.port,
            "public_base_url": settings.public_base_url,
            "default_model": settings.default_model,
            "default_effort": settings.default_effort,
            "max_concurrent_sessions": settings.max_concurrent_sessions,
            "enable_auto_prune_sessions": settings.enable_auto_prune_sessions,
            "max_retries": settings.max_retries,
            "initial_backoff": settings.initial_backoff,
            "cache_ttl_seconds": settings.cache_ttl_seconds,
            "usage_cache_ttl_seconds": settings.usage_cache_ttl_seconds,
            "image_cache_ttl_seconds": settings.image_cache_ttl_seconds,
            "image_cache_dir": str(settings.image_cache_dir),
            "resolved_agy_bin": settings.resolve_agy_bin(),
            "antigravity_home": str(settings.antigravity_home),
        }
