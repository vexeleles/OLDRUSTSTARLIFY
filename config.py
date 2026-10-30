# Основная конфигурация StarlifyShop
#
# Все секреты (токены) читаются из переменных окружения / файла .env
# и НИКОГДА не должны храниться в этом файле или коммититься в git.
# Скопируйте .env.example в .env и подставьте свои значения.

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    """Возвращает значение переменной окружения или завершает работу с понятной ошибкой."""
    value = os.getenv(name)
    if not value:
        sys.exit(
            f"❌ Не задана переменная окружения {name}.\n"
            f"   Создайте файл .env (см. .env.example) и укажите {name}=..."
        )
    return value


def _parse_admin_ids(raw: str) -> list[int]:
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            sys.exit(f"❌ ADMIN_IDS содержит некорректное значение: {part!r}")
    if not ids:
        sys.exit("❌ ADMIN_IDS не может быть пустым — укажите хотя бы один Telegram ID администратора.")
    return ids


# --- Обязательные секреты ---
BOT_TOKEN = _require_env("BOT_TOKEN")
CRYPTO_BOT_TOKEN = _require_env("CRYPTO_BOT_TOKEN")  # Токен из @CryptoBot -> Crypto Pay -> Apps

# --- Администраторы ---
ADMIN_IDS = _parse_admin_ids(_require_env("ADMIN_IDS"))

# --- Прочие настройки (не секретные, можно оставить как есть) ---
def _resolve_db_path(path: str) -> str:
    """Создаёт папку под базу. Если её создать/писать в неё нельзя (например, /data на хостинге
    без подключённого диска) — не падаем, а кладём базу рядом с ботом и предупреждаем."""
    try:
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        if not os.access(folder, os.W_OK):
            raise PermissionError(folder)
        return path
    except OSError as e:
        fallback = os.path.join(os.path.dirname(os.path.abspath(__file__)), "starlify_shop.db")
        print(f"⚠️  Не удалось использовать DB_PATH={path!r} ({e}). "
              f"База будет в {fallback}. На бесплатном хостинге она сотрётся при перезапуске — "
              f"подключите диск (Disk/Volume) или держите включённые бэкапы (BACKUP_HOURS).",
              file=sys.stderr)
        return fallback


DB_PATH = _resolve_db_path(os.getenv("DB_PATH", "starlify_shop.db"))
COMPANY_NAME = os.getenv("COMPANY_NAME", "StarlifyShop")
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "t.me/StarlifyAdmin")

# --- CryptoBot: тестовая сеть / прокси (опционально) ---
CRYPTO_BOT_TESTNET = os.getenv("CRYPTO_BOT_TESTNET", "false").lower() in ("1", "true", "yes")
CRYPTO_BOT_PROXY = os.getenv("CRYPTO_BOT_PROXY") or None

# --- Mini App (WebApp) магазина ---
# Публичный HTTPS-адрес, по которому доступен ВЕСЬ проект (бот сам отдаёт и сайт, и API).
# Пример: https://shop.example.com   (без слэша на конце не обязательно)
def _detect_public_url() -> str:
    """Адрес берём из SHOP_WEBAPP_URL, а если не задан — угадываем по переменным хостинга."""
    url = os.getenv("SHOP_WEBAPP_URL", "").strip()
    if not url:
        url = os.getenv("RENDER_EXTERNAL_URL", "").strip()          # Render
    if not url and os.getenv("RAILWAY_PUBLIC_DOMAIN"):               # Railway
        url = "https://" + os.environ["RAILWAY_PUBLIC_DOMAIN"].strip()
    return url.rstrip("/")


SHOP_WEBAPP_URL = _detect_public_url()
# Папка с мини-аппом (по умолчанию ../webapp рядом с bot/; в Docker — /app/webapp)
_here = os.path.dirname(os.path.abspath(__file__))
_sibling = os.path.join(os.path.dirname(_here), "webapp")
# Если есть папка ../webapp — берём её, иначе index.html лежит рядом (плоская структура)
WEBAPP_DIR = os.getenv("WEBAPP_DIR", _sibling if os.path.isdir(_sibling) else _here)

# --- Донаты / поддержка проекта ---
# TON-кошелёк и USDT(TRC20)-адрес показываются пользователю как реквизиты для ручного перевода
# (в дополнение к оплате через CryptoBot, которая создаётся автоматически).
DONATE_TON_ADDRESS = os.getenv("DONATE_TON_ADDRESS", "")
DONATE_USDT_ADDRESS = os.getenv("DONATE_USDT_ADDRESS", "")


# --- HTTP API для Mini App (см. webapi.py) ---
WEBAPI_ENABLED = os.getenv("WEBAPI_ENABLED", "true").lower() in ("1", "true", "yes")
WEBAPI_HOST = os.getenv("WEBAPI_HOST", "0.0.0.0")
# PORT выставляют Railway/Render/Fly — он в приоритете
WEBAPI_PORT = int(os.getenv("PORT") or os.getenv("WEBAPI_PORT", "8080"))
# Origin страницы магазина для CORS. Пусто = берётся из SHOP_WEBAPP_URL.
WEBAPI_ALLOWED_ORIGIN = os.getenv("WEBAPI_ALLOWED_ORIGIN", "")

# --- Автономность на бесплатных хостингах ---
# KEEPALIVE=true: бот сам «пингует» свой публичный адрес, чтобы бесплатный хостинг не усыплял его.
KEEPALIVE = os.getenv("KEEPALIVE", "false").lower() in ("1", "true", "yes")
# Как часто (в часах) присылать админу копию базы заказов в Telegram. 0 = отключить.
BACKUP_HOURS = float(os.getenv("BACKUP_HOURS", "6"))
# Как часто (сек) проверять неоплаченные CryptoBot-счета в фоне (автозакрытие заказов).
PAYMENT_WATCH_SECONDS = int(os.getenv("PAYMENT_WATCH_SECONDS", "45"))


# --- Обязательная подписка на канал(ы) ---
# REQUIRED_CHANNEL=@mychannel          (или несколько через запятую: @a,@b; или id вида -1001234567890)
# Бот должен быть АДМИНИСТРАТОРОМ канала, иначе Telegram не даёт проверить подписку.
# Для приватных каналов (id) добавьте REQUIRED_CHANNEL_LINK=https://t.me/+инвайт (через запятую в том же порядке).
# Пусто = подписка не требуется. Админы из ADMIN_IDS проверку не проходят.
REQUIRED_CHANNELS = [x.strip() for x in os.getenv("REQUIRED_CHANNEL", "").split(",") if x.strip()]
REQUIRED_CHANNEL_LINKS = [x.strip() for x in os.getenv("REQUIRED_CHANNEL_LINK", "").split(",") if x.strip()]
