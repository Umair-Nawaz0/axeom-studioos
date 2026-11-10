import json
import os
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from ..config import settings

_ACTIVE_REFERENCE_DATE: Optional[date] = None
_CACHED_LOCATION_DATE: Optional[Dict[str, Any]] = None
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS: float = 600.0  # 10 minutes cache to avoid excessive network calls


def detect_location_date(timeout_sec: float = 3.5, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Queries public date/time APIs to determine today's current date and time at the user's location.
    Gracefully falls back to system clock if network is unreachable or times out.
    """
    global _CACHED_LOCATION_DATE, _CACHE_TIMESTAMP
    now_ts = datetime.now(timezone.utc).timestamp()

    if not force_refresh and _CACHED_LOCATION_DATE is not None:
        if (now_ts - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS:
            return dict(_CACHED_LOCATION_DATE)

    location_info: Dict[str, Any] = {}

    # Step 1: Detect public IP
    ip_address = ""
    try:
        req_ip = urllib.request.Request(
            "https://api.ipify.org",
            headers={"User-Agent": "AxeomStudioOS/2.0 DateClient"},
        )
        with urllib.request.urlopen(req_ip, timeout=timeout_sec) as res:
            ip_address = res.read().decode("utf-8").strip()
    except Exception:
        ip_address = ""

    # Step 2: Query timeapi.io using IP if available, or fallback to UTC zone endpoint
    if ip_address:
        try:
            time_url = f"https://timeapi.io/api/time/current/ip?ipAddress={ip_address}"
            req_time = urllib.request.Request(
                time_url,
                headers={"User-Agent": "AxeomStudioOS/2.0 DateClient", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req_time, timeout=timeout_sec) as res:
                data = json.loads(res.read().decode("utf-8"))
                dt_str = data.get("dateTime")
                if dt_str:
                    dt = datetime.fromisoformat(dt_str)
                    d_iso = dt.date().isoformat()
                    location_info = {
                        "date": d_iso,
                        "time": data.get("time") or dt.strftime("%H:%M:%S"),
                        "timezone": data.get("timeZone") or "Location Detected",
                        "day_of_week": data.get("dayOfWeek") or dt.strftime("%A"),
                        "source": f"timeapi.io (location IP: {ip_address})",
                        "ip": ip_address,
                        "is_external_api": True,
                    }
        except Exception:
            location_info = {}

    if not location_info:
        # Fallback to general UTC zone on timeapi.io
        try:
            req_utc = urllib.request.Request(
                "https://timeapi.io/api/time/current/zone?timeZone=UTC",
                headers={"User-Agent": "AxeomStudioOS/2.0 DateClient", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req_utc, timeout=timeout_sec) as res:
                data = json.loads(res.read().decode("utf-8"))
                dt_str = data.get("dateTime")
                if dt_str:
                    dt = datetime.fromisoformat(dt_str)
                    location_info = {
                        "date": dt.date().isoformat(),
                        "time": data.get("time") or dt.strftime("%H:%M:%S"),
                        "timezone": "UTC",
                        "day_of_week": data.get("dayOfWeek") or dt.strftime("%A"),
                        "source": "timeapi.io (UTC zone fallback)",
                        "ip": ip_address or "unknown",
                        "is_external_api": True,
                    }
        except Exception:
            location_info = {}

    # Step 3: Local system clock fallback if external APIs are unreachable (e.g. offline sandbox)
    if not location_info:
        today_local = date.today()
        now_local = datetime.now()
        location_info = {
            "date": today_local.isoformat(),
            "time": now_local.strftime("%H:%M:%S"),
            "timezone": str(datetime.now().astimezone().tzinfo or "Local System"),
            "day_of_week": now_local.strftime("%A"),
            "source": "system_local_clock",
            "ip": ip_address or "127.0.0.1",
            "is_external_api": False,
        }

    _CACHED_LOCATION_DATE = location_info
    _CACHE_TIMESTAMP = now_ts
    return dict(location_info)


def get_active_reference_date() -> date:
    """
    Returns the currently active reference date for calculations.
    If explicitly overridden via set_active_reference_date() or os.environ["REFERENCE_DATE"], returns that override.
    Defaults at start to today's date (detected via location date API or system clock).
    """
    global _ACTIVE_REFERENCE_DATE
    if _ACTIVE_REFERENCE_DATE is not None:
        return _ACTIVE_REFERENCE_DATE

    env_date = os.getenv("REFERENCE_DATE")
    if env_date:
        try:
            return date.fromisoformat(env_date)
        except Exception:
            pass

    try:
        loc = detect_location_date()
        return date.fromisoformat(loc["date"])
    except Exception:
        return date.today()


def set_active_reference_date(new_date: date) -> date:
    """Sets a global reference date override for all calculations."""
    global _ACTIVE_REFERENCE_DATE
    _ACTIVE_REFERENCE_DATE = new_date
    return _ACTIVE_REFERENCE_DATE


def reset_active_reference_date() -> None:
    """Clears the global override, reverting to today's date."""
    global _ACTIVE_REFERENCE_DATE
    _ACTIVE_REFERENCE_DATE = None
