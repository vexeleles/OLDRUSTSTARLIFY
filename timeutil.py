# -*- coding: utf-8 -*-
"""Время по Киеву. Хостинг (Render и др.) работает в UTC, поэтому берём украинское время явно."""
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _KYIV = ZoneInfo("Europe/Kyiv")
except Exception:          # нет базы часовых поясов — считаем вручную (EET/EEST)
    _KYIV = None


def _last_sunday(year: int, month: int) -> datetime:
    d = datetime(year, month, 31 if month in (3, 10) else 30)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def now_kyiv() -> datetime:
    """Текущее время в Киеве (наивный datetime — удобно для strftime)."""
    if _KYIV is not None:
        return datetime.now(_KYIV).replace(tzinfo=None)
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    start = _last_sunday(utc.year, 3).replace(hour=1)     # 01:00 UTC последнего воскресенья марта
    end = _last_sunday(utc.year, 10).replace(hour=1)      # 01:00 UTC последнего воскресенья октября
    return utc + timedelta(hours=3 if start <= utc < end else 2)
