from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.core.settings import get_settings

settings = get_settings()

# ====== Timezone 配置 ======
APP_TZ = ZoneInfo(settings.APP_TIMEZONE)
UTC_TZ = ZoneInfo("UTC")

# ====== 格式 ======
FRONTEND_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
FRONTEND_DATETIME_FORMAT_ZH = "%Y年%m月%d日 %H:%M:%S"


# ====== 当前时间 ======
def now_utc() -> datetime:
    """当前 UTC 时间（aware）"""
    return datetime.now(UTC)


def now_app() -> datetime:
    """当前应用时区时间（aware）"""
    return datetime.now(APP_TZ)


# ====== 时区转换 ======
def ensure_aware(dt: datetime) -> datetime:
    """
    确保 datetime 是 aware
    默认策略：naive 当作 UTC（推荐统一约定）
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    dt = ensure_aware(dt)
    return dt.astimezone(UTC)


def to_app_tz(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    dt = ensure_aware(dt)
    return dt.astimezone(APP_TZ)


# ====== 格式化 ======
def format_dt(
    dt: datetime | None,
    fmt: str = FRONTEND_DATETIME_FORMAT,
    to_app: bool = True,
    drop_tz: bool = True,
) -> str | None:
    """
    通用格式化函数（核心函数）
    """
    if dt is None:
        return None

    dt = ensure_aware(dt)

    if to_app:
        dt = dt.astimezone(APP_TZ)

    if drop_tz:
        dt = dt.replace(tzinfo=None)

    return dt.strftime(fmt)


def format_frontend(dt: datetime | None) -> str | None:
    """前端标准格式"""
    return format_dt(dt)


def format_frontend_zh(dt: datetime | None) -> str | None:
    """中文格式"""
    return format_dt(dt, FRONTEND_DATETIME_FORMAT_ZH)


# ====== 解析 ======
def parse_datetime(
    s: str,
    fmt: str = FRONTEND_DATETIME_FORMAT,
    assume_tz: ZoneInfo = APP_TZ,
) -> datetime:
    """
    字符串 -> aware datetime
    """
    dt = datetime.strptime(s, fmt)
    return dt.replace(tzinfo=assume_tz)


def parse_date_flexible(s: str) -> datetime:
    """
    多格式解析（返回 aware datetime）
    """
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return parse_datetime(s, fmt)
        except ValueError:
            continue

    raise ValueError(f"无法解析日期字符串: {s}")
