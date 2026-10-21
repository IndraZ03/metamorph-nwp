from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import config
from .network import ssl_context

log = logging.getLogger("ecmwf.fetch")


def _get_client():
    from ecmwf.opendata import Client

    return Client(source=config.SOURCE)


def index_url(run_time: datetime, step: int) -> str:
    run_time = run_time.astimezone(timezone.utc)
    ymd = run_time.strftime("%Y%m%d")
    hh = run_time.strftime("%H")
    stamp = run_time.strftime("%Y%m%d%H0000")
    return (
        f"{config.INDEX_ROOT}/{ymd}/{hh}z/ifs/{config.RESOL}/{config.STREAM}/"
        f"{stamp}-{step}h-{config.STREAM}-fc.index"
    )


_UA = {"User-Agent": "metamorph-nwp-ecmwf-engine/0.1"}


def head_ok(url: str, timeout: int = 20) -> bool:
    req = Request(url, method="HEAD", headers=_UA)
    try:
        with urlopen(req, context=ssl_context(), timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except HTTPError as e:
        if e.code in (403, 405):
            return get_ok(url, timeout=timeout)
        return False
    except (URLError, TimeoutError, OSError):
        return False


def get_ok(url: str, timeout: int = 20) -> bool:
    req = Request(url, method="GET", headers=_UA)
    try:
        with urlopen(req, context=ssl_context(), timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def list_index_steps(run_time: datetime, candidates: list[int]) -> list[int]:
    found = []
    for step in candidates:
        if head_ok(index_url(run_time, step)):
            found.append(step)
    return found


def discover_latest_run(lookback_hours: int = 48) -> datetime | None:
    """Walk 00/06/12/18 UTC backward. First cycle with step-0 index wins."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hour = (now.hour // 6) * 6
    cursor = now.replace(hour=hour)
    end = cursor - timedelta(hours=lookback_hours)
    while cursor >= end:
        if cursor.hour in (0, 6, 12, 18) and head_ok(index_url(cursor, 0)):
            log.info("latest run with step 0 index: %s", cursor.isoformat())
            return cursor
        cursor -= timedelta(hours=6)
    return None


def retrieve_step(
    run_time: datetime,
    step: int,
    target: Path,
    params: list[str] | None = None,
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return target
    client = _get_client()
    tmp = target.with_suffix(".part")
    if tmp.exists():
        tmp.unlink()
    want = list(params or config.FETCH_PARAMS)
    log.info(
        "retrieve run=%s step=%s params=%s -> %s",
        run_time.isoformat(),
        step,
        ",".join(want),
        target.name,
    )
    client.retrieve(
        date=run_time.strftime("%Y-%m-%d"),
        time=int(run_time.strftime("%H")),
        stream=config.STREAM,
        type="fc",
        step=step,
        param=want,
        target=str(tmp),
    )
    tmp.replace(target)
    return target


def discover_via_client() -> datetime | None:
    """Ask ecmwf-opendata for the most recent matching request (no date/time)."""
    try:
        client = _get_client()
        if not hasattr(client, "latest"):
            return None
        latest = client.latest(
            stream=config.STREAM,
            type="fc",
            step=0,
            param="2t",
        )
        if latest is None:
            return None
        if isinstance(latest, datetime):
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            return latest.astimezone(timezone.utc)
        return None
    except Exception as e:
        log.warning("client.latest failed: %s", e)
        return None
