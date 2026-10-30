import html
import logging
import asyncio
import functools
import re
import time
import uuid
import aiohttp
import socket
import os
import shutil
import sqlite3
import tempfile
from timeutil import now_kyiv
from aiogram import BaseMiddleware, Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, TelegramObject,
    LabeledPrice, PreCheckoutQuery,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramServerError

import config
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
import premium_emoji
import database as db
import keyboards as kb
import locales as loc
import webapi
from states import BuyStars, BuyPremium, PaymentState, SupportState, AdminSettings, AdminBroadcast, DonateState

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
for noisy_logger in ("aiohttp", "aiohttp.client", "aiohttp.access", "aiogram", "aiogram.event", "asyncio"):
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

logger = logging.getLogger("starlify")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
premium_emoji.install(bot, dp)
router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS

def admin_only(handler):
    """Декоратор для хендлеров, доступных только администраторам.

    Заменяет повторяющееся `if not is_admin(...): return` в каждом
    admin-хендлере. Работает и для Message, и для CallbackQuery.
    """
    @functools.wraps(handler)
    async def wrapper(event, *args, **kwargs):
        if not is_admin(event.from_user.id):
            return
        return await handler(event, *args, **kwargs)
    return wrapper

class AntiFloodMiddleware(BaseMiddleware):
    """Простая защита от спама: не чаще одного апдейта в MIN_INTERVAL секунд на пользователя."""

    MIN_INTERVAL = 0.5  # секунд между сообщениями/нажатиями от одного пользователя

    def __init__(self):
        super().__init__()
        self._last_seen: dict[int, float] = {}

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            last = self._last_seen.get(user.id, 0.0)
            if now - last < self.MIN_INTERVAL:
                # Тихо игнорируем слишком частые апдейты, не отвечая пользователю,
                # чтобы не провоцировать ещё больше сообщений.
                return None
            self._last_seen[user.id] = now
        return await handler(event, data)

SUB_TEXTS = {
    "ru": {"text": "📢 Чтобы пользоваться ботом, подпишитесь на наш канал, затем нажмите «Я подписался».",
           "join": "📢 Подписаться", "check": "✅ Я подписался",
           "no": "Вы ещё не подписались на канал.", "ok": "✅ Подписка подтверждена!"},
    "en": {"text": "📢 To use the bot, please subscribe to our channel, then tap “I subscribed”.",
           "join": "📢 Subscribe", "check": "✅ I subscribed",
           "no": "You haven't subscribed to the channel yet.", "ok": "✅ Subscription confirmed!"},
    "ua": {"text": "📢 Щоб користуватися ботом, підпишіться на наш канал, потім натисніть «Я підписався».",
           "join": "📢 Підписатися", "check": "✅ Я підписався",
           "no": "Ви ще не підписалися на канал.", "ok": "✅ Підписку підтверджено!"},
}


class SubscriptionMiddleware(BaseMiddleware):
    """Пускает к боту только подписанных на REQUIRED_CHANNEL(ы). Админы проходят без проверки.
    Если проверить нельзя (бот не админ канала и т.п.) — не блокируем, чтобы не положить бота."""

    OK_TTL = 120  # секунд помним, что пользователь подписан

    def __init__(self):
        super().__init__()
        self._ok_until: dict[int, float] = {}
        self._pending_start: dict[int, Message] = {}
        self._urls: dict[str, str | None] = {}

    @staticmethod
    def _norm(ch: str) -> str:
        """@name, name, t.me/name, https://t.me/name  ->  name ; числовой id остаётся как есть."""
        ch = ch.strip()
        for p in ("https://", "http://"):
            if ch.startswith(p):
                ch = ch[len(p):]
        for p in ("t.me/", "telegram.me/"):
            if ch.startswith(p):
                ch = ch[len(p):]
        return ch.split("?")[0].strip("/").lstrip("@")

    @classmethod
    def _chat_ref(cls, ch: str):
        ch = cls._norm(ch)
        return int(ch) if ch.lstrip("-").isdigit() else "@" + ch

    async def _channel_url(self, i: int, ch: str):
        """Ссылка для кнопки «Подписаться»: из имени канала, из REQUIRED_CHANNEL_LINK или от самого Telegram."""
        name = self._norm(ch)
        if not name.lstrip("-").isdigit() and not name.startswith("+"):
            return "https://t.me/" + name
        if i < len(config.REQUIRED_CHANNEL_LINKS):
            return config.REQUIRED_CHANNEL_LINKS[i]
        if ch in self._urls:
            return self._urls[ch]
        url = None
        try:
            chat = await bot.get_chat(self._chat_ref(ch))
            url = ("https://t.me/" + chat.username) if chat.username else chat.invite_link
        except Exception as e:
            logging.warning(f"Не удалось получить ссылку канала {ch}: {e}")
        self._urls[ch] = url
        return url

    async def _is_subscribed(self, uid: int) -> bool:
        if self._ok_until.get(uid, 0) > time.monotonic():
            return True
        for ch in config.REQUIRED_CHANNELS:
            try:
                member = await bot.get_chat_member(self._chat_ref(ch), uid)
            except Exception as e:
                logging.warning(f"Проверка подписки на {ch} невозможна ({e}) — пропускаю. Бот должен быть админом канала.")
                continue
            ok = member.status in ("creator", "administrator", "member") or (
                member.status == "restricted" and getattr(member, "is_member", False))
            if not ok:
                return False
        self._ok_until[uid] = time.monotonic() + self.OK_TTL
        return True

    async def _keyboard(self, lang: str):
        t = SUB_TEXTS.get(lang, SUB_TEXTS["ru"])
        rows = []
        for i, ch in enumerate(config.REQUIRED_CHANNELS):
            url = await self._channel_url(i, ch)
            if url:
                rows.append([InlineKeyboardButton(text=t["join"], url=url)])
        rows.append([InlineKeyboardButton(text=t["check"], callback_data="check_sub")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if not config.REQUIRED_CHANNELS or user is None or user.id in config.ADMIN_IDS or user.is_bot:
            return await handler(event, data)
        if isinstance(event, Message) and event.chat.type != "private":
            return await handler(event, data)
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        lang = db.get_language(user.id)
        t = SUB_TEXTS.get(lang, SUB_TEXTS["ru"])

        # кнопка «Я подписался»
        if isinstance(event, CallbackQuery) and event.data == "check_sub":
            self._ok_until.pop(user.id, None)
            if not await self._is_subscribed(user.id):
                await event.answer(t["no"], show_alert=True)
                return None
            await event.answer(t["ok"])
            try:
                await event.message.delete()
            except Exception:
                pass
            pending = self._pending_start.pop(user.id, None)
            if pending is not None:  # возвращаем пользователя к его /start (с реферальной ссылкой и т.п.)
                from aiogram.types import Update
                await dp.feed_update(bot, Update(update_id=0, message=pending))
            else:
                await bot.send_message(user.id, t["ok"], reply_markup=kb.main_menu(lang))
            return None

        if await self._is_subscribed(user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            if (event.text or "").startswith("/start"):
                self._pending_start[user.id] = event
            await event.answer(t["text"], reply_markup=await self._keyboard(lang))
        else:
            await event.answer(t["no"], show_alert=True)
            await bot.send_message(user.id, t["text"], reply_markup=await self._keyboard(lang))
        return None

async def validate_tg_username(text: str) -> bool:
    clean = text.strip().replace("https://t.me/", "").replace("@", "")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$", clean):
        return True
    return False

# Курсы для отображения суммы в других валютах (грн -> $ / TON).
# Вынесены в константы, чтобы не дублировать магические числа по всему файлу.
UAH_TO_USD = 0.024
UAH_TO_TON = 0.0035

def _float_setting(key: str, default: float) -> float:
    try:
        v = float(db.get_setting(key) or 0)
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default

def get_uah_to_usd() -> float:
    """Сколько долларов в одной гривне — по курсу, заданному админом (usd_rate)."""
    return 1 / _float_setting("usd_rate", 1 / UAH_TO_USD)

def get_ton_uah_manual():
    """Ручной курс TON (грн за 1 TON) или None, если стоит 0 (авто из CryptoBot)."""
    v = _float_setting("ton_rate", 0.0)
    return v or None

def get_uah_to_ton() -> float:
    manual = get_ton_uah_manual()
    return 1 / manual if manual else UAH_TO_TON

def get_stars_min() -> int:
    return max(1, int(_float_setting("stars_min", 50)))

def get_multicurrency_string(amount_uah: float) -> str:
    usd = round(amount_uah * get_uah_to_usd(), 2)
    ton = round(amount_uah * get_uah_to_ton(), 3)
    return f"{amount_uah} грн | {usd} $ | {ton} TON"

def format_order_receipt(order_num, date, item, details, price_str, target, lang="ru", discount_note=None):
    discount_line = f"🎉 {discount_note}\n" if discount_note else ""
    return (
        f"🧾 {config.COMPANY_NAME}\n"
        f"————————————————————————\n"
        f"{loc.t('receipt.header', lang)}: {order_num}\n"
        f"{loc.t('receipt.date', lang)}: {date}\n"
        f"{loc.t('receipt.item', lang)}: {item} ({details})\n"
        f"{loc.t('receipt.recipient', lang)}: {target}\n"
        f"{loc.t('receipt.price', lang)}: {price_str}\n"
        f"{discount_line}"
        f"————————————————————————\n"
        f"{loc.t('receipt.status_pending', lang)}"
    )

async def notify_management(text: str, proof_id: str = None, proof_type: str = None, reply_markup=None):
    for admin_id in config.ADMIN_IDS:
        try:
            if proof_id and proof_type == "PHOTO":
                await bot.send_photo(chat_id=admin_id, photo=proof_id, caption=text, reply_markup=reply_markup)
            elif proof_id and proof_type == "PDF":
                await bot.send_document(chat_id=admin_id, document=proof_id, caption=text, reply_markup=reply_markup)
            else:
                await bot.send_message(chat_id=admin_id, text=text, reply_markup=reply_markup)
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)

# ============== CRYPTOBOT ==============

# Активы, поддерживаемые Crypto Pay API для инвойсов с currency_type="crypto".
SUPPORTED_CRYPTO_ASSETS = ("USDT", "TON", "BTC", "ETH", "LTC", "BNB", "TRX", "USDC")

async def _cryptobot_request(method: str, endpoint: str, *, json_payload: dict | None = None,
                              params: dict | None = None) -> tuple[dict | None, str]:
    """Общий helper для запросов к Crypto Pay API (createInvoice/getInvoices/...).

    Вынесен из create_cryptobot_invoice/safe_check_invoice, чтобы не дублировать
    обработку сети/таймаутов/ошибок в каждой новой функции работы с CryptoBot.
    Возвращает (result, error_message) — как и раньше.
    """
    is_testnet = getattr(config, "CRYPTO_BOT_TESTNET", False)
    base_url = "https://testnet-pay.crypt.bot" if is_testnet else "https://pay.crypt.bot"
    url = f"{base_url}/api/{endpoint}"
    headers = {"Crypto-Pay-API-Token": config.CRYPTO_BOT_TOKEN}
    proxy = getattr(config, "CRYPTO_BOT_PROXY", None)
    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=False)
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            if method == "POST":
                request_cm = session.post(url, json=json_payload, headers=headers, proxy=proxy)
            else:
                request_cm = session.get(url, headers=headers, params=params, proxy=proxy)
            async with request_cm as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("ok"):
                        return data["result"], ""
                    return None, f"CryptoBot отказал: {data.get('description', 'Неизвестная ошибка API')}"
                else:
                    err_body = await r.text()
                    return None, f"Код сервера {r.status}. Ответ: {err_body}"
    except aiohttp.ClientConnectorError as e:
        return None, f"Ошибка подключения к {base_url}. Скорее всего, домен заблокирован вашим провайдером. Тех. инфо: {e}"
    except asyncio.TimeoutError:
        return None, "Превышено время ожидания ответа от CryptoBot (Таймаут 15 сек)."
    except Exception as e:
        return None, f"Внутренний сбой скрипта: {e}"

async def create_cryptobot_invoice(amount_usd: float, order_num: str) -> tuple[dict | None, str]:
    """Создаёт инвойс в фиатном эквиваленте (USD) — используется для заказов магазина и донатов.
    Пользователь платит в USDT/TON по курсу CryptoBot на момент оплаты."""
    payload = {
        "currency_type": "fiat",
        "fiat": "USD",
        "amount": str(amount_usd),
        "accepted_assets": "USDT,TON",
        "description": f"Оплата заказа {order_num} в {config.COMPANY_NAME}"
    }
    return await _cryptobot_request("POST", "createInvoice", json_payload=payload)

async def create_cryptobot_crypto_invoice(amount: str, asset: str, description: str) -> tuple[dict | None, str]:
    """Создаёт инвойс на точную сумму в конкретной криптовалюте (не в фиате).

    В отличие от create_cryptobot_invoice (курс USD -> крипта считает сам CryptoBot),
    здесь сумма и актив фиксированы явно. Используется для тестовых платежей
    администратора (/create 0.00001 USDT), где важно выставить именно ту сумму,
    которую попросили, а не её ближайший фиатный эквивалент.
    """
    payload = {
        "currency_type": "crypto",
        "asset": asset,
        "amount": str(amount),
        "description": description,
    }
    return await _cryptobot_request("POST", "createInvoice", json_payload=payload)

async def safe_check_invoice(invoice_id: int) -> tuple[dict | None, str]:
    result, error_msg = await _cryptobot_request("GET", "getInvoices", params={"invoice_ids": str(invoice_id)})
    if result is None:
        return None, error_msg
    items = result.get("items") if isinstance(result, dict) else None
    if not items:
        return None, "Инвойс не найден в системе."
    return items[0], ""

# ============== HELPERS ==============

def get_stars_discount_percent() -> float:
    """Возвращает текущий активный процент скидки на звёзды (0, если скидка выключена)."""
    if db.get_setting("stars_discount_enabled") != "1":
        return 0.0
    try:
        pct = float(db.get_setting("stars_discount_percent") or 0)
    except (TypeError, ValueError):
        pct = 0.0
    return max(0.0, min(pct, 100.0))

def get_stars_discount_text(percent: float) -> str:
    """Возвращает текст объявления о скидке, подставляя {percent} из шаблона в настройках."""
    template = db.get_setting("stars_discount_text") or "🎉 СКИДКА -{percent}%!"
    return template.replace("{percent}", f"{percent:g}")

def apply_stars_discount(amount_uah: float, percent: float) -> float:
    """Применяет скидку (в процентах) к сумме и округляет до копеек."""
    if percent <= 0:
        return round(amount_uah, 2)
    return round(amount_uah * (1 - percent / 100), 2)

def _stars_catalog_text(rate: float) -> str:
    """Формирует текст каталога звёзд с ценами для каждого пресета, с учётом скидки."""
    presets = [50, 100, 250, 500, 1000]
    discount = get_stars_discount_percent()

    lines = []
    if discount > 0:
        lines.append(get_stars_discount_text(discount) + "\n")
    lines.append("⭐ Каталог звёзд — выберите пакет:\n")

    for qty in presets:
        base_price = round(qty * rate, 2)
        if discount > 0:
            final_price = apply_stars_discount(base_price, discount)
            usd = round(final_price * get_uah_to_usd(), 2)
            lines.append(f"  • {qty} Stars → {final_price} грн / {usd} $  (было {base_price} грн, -{discount:g}%)")
        else:
            usd = round(base_price * get_uah_to_usd(), 2)
            lines.append(f"  • {qty} Stars → {base_price} грн / {usd} $")

    lines.append(f"\nМинимальный заказ: {get_stars_min()} Stars.")
    return "\n".join(lines)

async def _cancel_if_in_buy_fsm(message: Message, state: FSMContext, lang: str) -> bool:
    """Если пользователь в процессе покупки — отменяем и возвращаем True."""
    current = await state.get_state()
    buy_states = {
        BuyStars.get_count.state,
        BuyStars.get_username.state,
        BuyPremium.get_username.state,
    }
    donate_states = {
        DonateState.get_stars_amount.state,
        DonateState.get_crypto_amount.state,
    }
    if current in buy_states:
        await state.clear()
        await message.answer(
            "❌ Заказ отклонён — вы нажали другую кнопку во время оформления.",
            reply_markup=kb.main_menu(lang)
        )
        return True
    if current in donate_states:
        await state.clear()
        await message.answer(loc.t("donate.cancelled", lang), reply_markup=kb.main_menu(lang))
        return True
    return False

async def _antispam_check(user_id: int, message_or_callback) -> bool:
    """Проверяет антиспам. Возвращает True если у пользователя есть незакрытый заказ."""
    open_order = db.get_open_order(user_id)
    if open_order:
        oid, onum, ostatus = open_order
        text = (
            f"⚠️ У вас уже есть незакрытый заказ!\n\n"
            f"Номер: {onum}\n"
            f"Статус: {loc.order_status_label(ostatus)}\n\n"
            f"Завершите или отмените его прежде чем создавать новый.\n"
            f"Проверить заказ: /status {onum}"
        )
        kb_cancel = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить старый заказ", callback_data=f"cancel_order_{oid}")]
        ])
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text, reply_markup=kb_cancel)
        else:
            await message_or_callback.message.answer(text, reply_markup=kb_cancel)
            await message_or_callback.answer()
        return True
    return False

# ============== USER HANDLERS ==============


async def send_receipt(order, user_id: int):
    """Красивый чек после выполнения заказа + кнопки «Отзыв» и «Повторить»."""
    lang = db.get_language(user_id)
    L = {"ru": ("ЧЕК ЗАКАЗА", "Заказ", "Товар", "Сумма", "Дата", "⭐ Оставить отзыв", "🔁 Повторить заказ"),
         "en": ("ORDER RECEIPT", "Order", "Item", "Total", "Date", "⭐ Leave a review", "🔁 Order again"),
         "ua": ("ЧЕК ЗАМОВЛЕННЯ", "Замовлення", "Товар", "Сума", "Дата", "⭐ Залишити відгук", "🔁 Повторити замовлення")}.get(lang) or None
    if L is None:
        L = ("ЧЕК ЗАКАЗА", "Заказ", "Товар", "Сумма", "Дата", "⭐ Оставить отзыв", "🔁 Повторить заказ")
    item = f"{order[3]} ⭐" if order[2] == "STARS" else f"Premium — {order[3]}"
    text = (f"{loc.t('notify.completed', lang)}\n\n"
            f"🧾 <b>{L[0]}</b>\n━━━━━━━━━━━━━━\n"
            f"{L[1]}: <code>{html.escape(str(order[10]))}</code>\n"
            f"{L[2]}: <b>{html.escape(item)}</b>\n"
            f"{L[3]}: <b>{float(order[4]):.2f} грн</b>\n"
            f"{L[4]}: {html.escape(str(order[9] or ''))}\n━━━━━━━━━━━━━━")
    rows = []
    link = (db.get_setting("reviews_link") or "").strip()
    if link:
        if not link.startswith("http"):
            link = "https://" + link
        rows.append([InlineKeyboardButton(text=L[5], url=link)])
    if config.SHOP_WEBAPP_URL:
        rows.append([InlineKeyboardButton(text=L[6], web_app=WebAppInfo(url=config.SHOP_WEBAPP_URL))])
    try:
        await bot.send_message(user_id, text, parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None)
    except Exception:
        logger.warning("Не удалось отправить чек", exc_info=True)


_INLINE_TXT = {"ru": ("⭐ Telegram Stars и Premium выгодно", "Покупай звёзды и Premium в Starlify Shop. Заходи по моей ссылке:", "🚀 Открыть магазин"),
               "en": ("⭐ Telegram Stars & Premium", "Buy Stars and Premium at Starlify Shop. Join via my link:", "🚀 Open shop"),
               "ua": ("⭐ Telegram Stars та Premium вигідно", "Купуй зірки та Premium у Starlify Shop. Заходь за моїм посиланням:", "🚀 Відкрити магазин")}

@router.inline_query()
async def inline_share(q: InlineQuery):
    try:
        lang = db.get_language(q.from_user.id)
        title, body, btn = _INLINE_TXT.get(lang, _INLINE_TXT["ru"])
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=ref{q.from_user.id}"
        res = InlineQueryResultArticle(
            id="share", title=title, description=body,
            input_message_content=InputTextMessageContent(message_text=f"<b>{title}</b>\n\n{body}", parse_mode="HTML"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=btn, url=link)]]),
        )
        await q.answer([res], cache_time=60, is_personal=True)
    except Exception:
        logger.warning("inline_query: ошибка", exc_info=True)

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    referrer_id = None
    buy_payload = None
    if len(args) > 1:
        param = args[1]
        if param.startswith("ref"):
            try:
                referrer_id = int(param[3:])
            except ValueError:
                referrer_id = None
        elif param.startswith("buy_"):
            buy_payload = param

    is_new = db.add_user(message.from_user.id, message.from_user.username, referrer_id)
    logging.info(f"Пользователь {message.from_user.id} запустил бота.")
    if is_new:
        try:
            _lc = (message.from_user.language_code or "").lower()[:2]
            db.set_language(message.from_user.id, {"uk": "ua", "en": "en"}.get(_lc, "ru"))
        except Exception:
            logger.warning("Не удалось определить язык", exc_info=True)
    lang = db.get_language(message.from_user.id)

    welcome = loc.t("start.welcome", lang)
    _d = os.path.dirname(os.path.abspath(__file__))
    banner = next((x for x in (os.path.join(_d, "assets", "banner.png"), os.path.join(_d, "banner.png")) if os.path.exists(x)), "")
    try:
        from aiogram.types import FSInputFile
        if os.path.exists(banner) and len(welcome) <= 1024:
            await message.answer_photo(FSInputFile(banner), caption=welcome, reply_markup=kb.main_menu(lang))
        else:
            await message.answer(welcome, reply_markup=kb.main_menu(lang))
    except Exception:
        await message.answer(welcome, reply_markup=kb.main_menu(lang))

    if is_new and referrer_id and referrer_id != message.from_user.id:
        try:
            ref_lang = db.get_language(referrer_id)
            uname = message.from_user.username or str(message.from_user.id)
            await bot.send_message(referrer_id, loc.t("ref.new_referral", ref_lang, username=uname))
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)

    if buy_payload:
        if buy_payload.startswith("buy_stars_"):
            qty_str = buy_payload[len("buy_stars_"):]
            if qty_str.isdigit():
                await state.update_data(count=int(qty_str))
                await message.answer(loc.t("site.stars_username", lang))
                await state.set_state(BuyStars.get_username)
        elif buy_payload in ("buy_prem_3m", "buy_prem_6m", "buy_prem_1y"):
            await message.answer(loc.t("site.prem_choose", lang), reply_markup=kb.premium_choice_kb())
        elif buy_payload == "buy_prem_login":
            await state.set_state(SupportState.active_chat)
            await message.answer(loc.t("site.prem_login_via_site", lang), reply_markup=kb.close_support_kb())

@router.message(F.text.in_(loc.all_variants("menu.profile")))
async def user_profile(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if await _cancel_if_in_buy_fsm(message, state, lang): return
    u = db.get_user(message.from_user.id)
    if not u: return
    ref_count, ref_balance = db.get_ref_stats(message.from_user.id)
    text = (
        f"{loc.t('profile.title', lang)}\n\n"
        f"{loc.t('profile.id', lang)}: {u[0]}\n"
        f"{loc.t('profile.username', lang)}: @{u[1] if u[1] else loc.t('profile.not_set', lang)}\n"
        f"{loc.t('profile.reg_date', lang)}: {u[2]}\n"
        f"{loc.t('profile.orders_count', lang)}: {u[3]}\n"
        f"{loc.t('profile.total_spent', lang)}: {u[4]} грн\n\n"
        f"🤝 {loc.t('profile.ref_count', lang)}: {ref_count}\n"
        f"💰 {loc.t('profile.ref_balance', lang)}: {ref_balance:.2f} грн"
    )
    await message.answer(text)

def _referral_text(lang, ref_link, ref_count, ref_balance, bonus_percent, ref_earned=0.0, ref_bonus=0.0):
    return (
        f"{loc.t('referral.title', lang)}\n\n"
        f"{loc.t('referral.desc', lang, pct=bonus_percent)}\n\n"
        f"{loc.t('referral.link', lang)}:\n{ref_link}\n\n"
        f"{loc.t('referral.invited', lang)}: {ref_count}\n"
        f"{loc.t('referral.earned', lang)}: {ref_earned:.2f} грн\n"
        f"{loc.t('referral.bonus', lang)}: {ref_bonus:.2f} грн\n"
        f"{loc.t('referral.balance', lang)}: {ref_balance:.2f} грн\n\n"
        f"{loc.t('referral.usage_hint', lang)}"
    )

@router.message(F.text.in_(loc.all_variants("menu.referral")))
async def referral_program(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if await _cancel_if_in_buy_fsm(message, state, lang): return
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{message.from_user.id}"
    ref_count, ref_balance = db.get_ref_stats(message.from_user.id)
    bonus_percent = db.get_setting("referral_bonus_percent") or "5"
    ref_bonus = db.get_ref_bonus(message.from_user.id)
    text = _referral_text(lang, ref_link, ref_count, ref_balance, bonus_percent, db.get_ref_earned(message.from_user.id), ref_bonus)
    await message.answer(text, reply_markup=kb.referral_kb(ref_balance, ref_bonus))

@router.callback_query(F.data == "ref_refresh")
async def referral_refresh(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    ref_count, ref_balance = db.get_ref_stats(callback.from_user.id)
    bonus_percent = db.get_setting("referral_bonus_percent") or "5"
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{callback.from_user.id}"
    ref_bonus = db.get_ref_bonus(callback.from_user.id)
    text = _referral_text(lang, ref_link, ref_count, ref_balance, bonus_percent, db.get_ref_earned(callback.from_user.id), ref_bonus)
    try:
        await callback.message.edit_text(text, reply_markup=kb.referral_kb(ref_balance, ref_bonus))
    except Exception:
        logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)
    await callback.answer("Обновлено" if lang == "ru" else ("Updated" if lang == "en" else "Оновлено"))

@router.callback_query(F.data == "ref_transfer")
async def referral_transfer(callback: CallbackQuery):
    """Переводит реферальный баланс на основной (им можно оплачивать заказы)."""
    uid = callback.from_user.id
    lang = db.get_language(uid)
    amount = db.transfer_ref_bonus(uid)
    if amount <= 0:
        await callback.answer("Нет реферальных бонусов для перевода.", show_alert=True)
        return
    await callback.answer(f"✅ {amount:.2f} грн переведено на ваш баланс", show_alert=True)
    ref_count, ref_balance = db.get_ref_stats(uid)
    bonus_percent = db.get_setting("referral_bonus_percent") or "5"
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref{uid}"
    ref_bonus = db.get_ref_bonus(uid)
    text = _referral_text(lang, ref_link, ref_count, ref_balance, bonus_percent, db.get_ref_earned(uid), ref_bonus)
    try:
        await callback.message.edit_text(text, reply_markup=kb.referral_kb(ref_balance, ref_bonus))
    except Exception:
        logger.warning("Не удалось обновить сообщение рефералки", exc_info=True)

@router.callback_query(F.data == "ref_info_usage")
async def referral_usage_info(callback: CallbackQuery):
    await callback.answer(
        "Оформите заказ и выберите «💰 Оплатить с баланса» — сумма спишется автоматически.",
        show_alert=True
    )

@router.message(F.text.in_(loc.all_variants("menu.settings")))
async def settings_menu(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if await _cancel_if_in_buy_fsm(message, state, lang): return
    await message.answer(
        f"{loc.t('settings.title', lang)}\n\n{loc.t('settings.current_lang', lang)}: {loc.LANG_NAMES.get(lang, loc.LANG_NAMES['ru'])}",
        reply_markup=kb.settings_kb()
    )

@router.callback_query(F.data == "settings_language")
async def settings_language(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    await callback.message.edit_text(loc.t("settings.choose_lang", lang), reply_markup=kb.language_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("lang_"))
async def set_language_handler(callback: CallbackQuery):
    lang_code = callback.data.split("_")[1]
    db.set_language(callback.from_user.id, lang_code)
    confirm_texts = {
        "ru": "✅ Язык переключен на Русский.",
        "en": "✅ Language switched to English.",
        "ua": "✅ Мову змінено на Українську."
    }
    await callback.message.edit_text(confirm_texts.get(lang_code, confirm_texts["ru"]))
    await callback.answer()
    await callback.message.answer(
        loc.t("start.welcome", lang_code).split("\n\n")[0],
        reply_markup=kb.main_menu(lang_code)
    )

@router.message(F.text.in_(loc.all_variants("menu.orders")))
async def user_orders(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if await _cancel_if_in_buy_fsm(message, state, lang): return
    orders = db.get_user_orders(message.from_user.id)
    if not orders:
        await message.answer(loc.t("orders.empty", lang))
        return
    
    text = loc.t("orders.history", lang) + "\n\n"
    for o in orders[:10]:
        text += (
            f"{loc.t('orders.item_order', lang)}: {o[6]}\n"
            f"{loc.t('orders.item_product', lang)}: {o[1]} [{o[2]}]\n"
            f"{loc.t('orders.item_sum', lang)}: {o[3]} грн | {loc.t('orders.item_status', lang)}: {loc.order_status_label(o[4], lang)}\n"
            f"{loc.t('orders.item_date', lang)}: {o[5]}\n"
            f"————————————————————————\n"
        )
    await message.answer(text)

@router.message(F.text.in_(loc.all_variants("menu.reviews")))
async def user_reviews(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if await _cancel_if_in_buy_fsm(message, state, lang): return
    link = db.get_setting("reviews_link")
    await message.answer(loc.t("reviews.text", lang, link=link))

# --- СТАТУС ЗАКАЗА ---

@router.message(Command("status"), StateFilter("*"))
async def cmd_status(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "ℹ️ Синтаксис: /status НОМЕР_ЗАКАЗА\n\n"
            "Пример: /status ORD-20250628-A1B2C3D4"
        )
        return
    
    order_num = parts[1].strip().upper()
    order = db.get_order_by_num(order_num)
    
    if not order:
        await message.answer(f"❌ Заказ <b>{order_num}</b> не найден в базе.", parse_mode="HTML")
        return
    
    # Проверяем, что заказ принадлежит пользователю (или это админ)
    if order[1] != message.from_user.id and not is_admin(message.from_user.id):
        await message.answer("🚫 Этот заказ не принадлежит вашему аккаунту.")
        return
    
    lang = db.get_language(message.from_user.id)
    text = (
        f"📦 Информация о заказе\n"
        f"————————————————————————\n"
        f"Номер: {order[10]}\n"
        f"Товар: {order[2]} ({order[3]})\n"
        f"Сумма: {get_multicurrency_string(order[4])}\n"
        f"Получатель: {order[8]}\n"
        f"Дата: {order[9]}\n"
        f"Статус: {loc.order_status_label(order[5], lang)}\n"
        f"————————————————————————"
    )
    
    # Если заказ активен — показываем кнопку отмены
    open_statuses = ("НОВЫЙ", "ОЖИДАНИЕ_ОПЛАТЫ", "НА_ПРОВЕРКЕ", "НА_РАССМОТРЕНИИ")
    if order[5] in open_statuses:
        cancel_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order_{order[0]}")]
        ])
        await message.answer(text, reply_markup=cancel_markup)
    else:
        await message.answer(text)

# --- ПОКУПКА ЗВЕЗД ---

@router.message(F.text.in_(loc.all_variants("menu.buy_stars")))
async def buy_stars_start(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    # Автоотмена: если уже в процессе покупки
    if await _cancel_if_in_buy_fsm(message, state, lang):
        return

    # Антиспам: нельзя создать заказ, пока есть незакрытый
    if await _antispam_check(message.from_user.id, message):
        return

    rate = float(db.get_setting("stars_rate"))
    catalog_text = _stars_catalog_text(rate)
    await message.answer(catalog_text, reply_markup=kb.stars_preset_kb(lang))
    await state.set_state(BuyStars.get_count)

@router.callback_query(F.data == "stars_cancel")
async def stars_cancel_any(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await state.clear()
    await callback.message.answer("Покупка звёзд отменена.", reply_markup=kb.main_menu(lang))
    await callback.answer()

@router.callback_query(F.data == "premium_cancel")
async def premium_cancel_handler(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await state.clear()
    await callback.message.answer("Покупка Premium отменена.", reply_markup=kb.main_menu(lang))
    await callback.answer()

@router.callback_query(F.data.startswith("stars_preset_"), StateFilter(BuyStars.get_count, BuyStars.get_username))
async def stars_preset_chosen(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    preset = callback.data.split("_")[2]

    # Пользователь мог уже выбрать пресет раньше (état = get_username) и сейчас
    # кликает другую кнопку каталога — например, промахнулся и жмёт "50", а хотел
    # "Своё количество". Раньше это просто "зависало" (кнопка не отвечала), потому
    # что хендлер слушал только состояние get_count. Теперь ловим клик в обоих
    # состояниях и просто переоформляем выбор с нуля — старый выбор отменяется.
    await state.update_data(count=None, amount_uah=None, base_amount=None, discount_percent=None)

    if preset == "custom":
        await callback.message.answer(
            f"✏️ Введите количество звёзд (минимум {get_stars_min()}):",
            reply_markup=kb.cancel_kb(lang)
        )
        await state.set_state(BuyStars.get_count)
        await callback.answer()
        return

    count = int(preset)
    rate = float(db.get_setting("stars_rate"))
    base_amount = round(count * rate, 2)
    discount = get_stars_discount_percent()
    amount_uah = apply_stars_discount(base_amount, discount)
    price_str = get_multicurrency_string(amount_uah)

    discount_line = f"🎉 Скидка -{discount:g}%: было {base_amount} грн\n" if discount > 0 else ""
    await state.update_data(count=count, amount_uah=amount_uah, base_amount=base_amount, discount_percent=discount)
    await callback.message.answer(
        f"✅ Выбрано: {count} Stars\n{discount_line}💰 Цена: {price_str}\n\nВведите Telegram-юзернейм получателя (@username):",
        reply_markup=kb.username_entry_kb(lang, callback.from_user.username)
    )
    await state.set_state(BuyStars.get_username)
    await callback.answer()

@router.message(BuyStars.get_count)
async def buy_stars_count(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    if message.text in kb.CANCEL_TEXTS:
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.main_menu(lang))
        return

    if message.text in loc.all_menu_variants():
        await state.clear()
        await message.answer("❌ Заказ отклонён — вы нажали другую кнопку во время оформления.", reply_markup=kb.main_menu(lang))
        return

    if not message.text.isdigit() or int(message.text) < get_stars_min():
        await message.answer(f"❌ Введите число {get_stars_min()} или больше.")
        return
    count = int(message.text)

    rate = float(db.get_setting("stars_rate"))
    base_amount = round(count * rate, 2)
    discount = get_stars_discount_percent()
    amount_uah = apply_stars_discount(base_amount, discount)
    price_str = get_multicurrency_string(amount_uah)

    discount_line = f"🎉 Скидка -{discount:g}%: было {base_amount} грн\n" if discount > 0 else ""
    await state.update_data(count=count, amount_uah=amount_uah, base_amount=base_amount, discount_percent=discount)
    await message.answer(
        f"✅ Выбрано: {count} Stars\n{discount_line}💰 Цена: {price_str}\n\n" + loc.t("stars.enter_username", lang),
        reply_markup=kb.username_entry_kb(lang, message.from_user.username)
    )
    await state.set_state(BuyStars.get_username)

@router.message(BuyStars.get_username)
async def buy_stars_username(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    if message.text in kb.CANCEL_TEXTS:
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.main_menu(lang))
        return

    if message.text in loc.all_menu_variants():
        await state.clear()
        await message.answer("❌ Заказ отклонён — вы нажали другую кнопку во время оформления.", reply_markup=kb.main_menu(lang))
        return

    # Кнопка "Свой юзернейм"
    if message.text in kb.MY_USERNAME_TEXTS:
        if not message.from_user.username:
            await message.answer("❌ У вас не установлен юзернейм в Telegram. Введите юзернейм вручную.")
            return
        target = f"@{message.from_user.username}"
    else:
        target = message.text.strip()
    if not await validate_tg_username(target):
        await message.answer(loc.t("stars.bad_username", lang))
        return
    
    data = await state.get_data()
    count = data['count']
    # Сумма со скидкой уже посчитана и показана на предыдущем шаге — переиспользуем её,
    # чтобы цена в чеке не "поплыла", даже если админ поменяет скидку между шагами.
    discount_percent = data.get('discount_percent', 0)
    base_amount = data.get('base_amount')
    amount_uah = data.get('amount_uah')
    if amount_uah is None:
        rate = float(db.get_setting("stars_rate"))
        base_amount = round(count * rate, 2)
        discount_percent = get_stars_discount_percent()
        amount_uah = apply_stars_discount(base_amount, discount_percent)
    price_str = get_multicurrency_string(amount_uah)

    order_id, order_num = db.create_order(message.from_user.id, "STARS", str(count), amount_uah, target)
    await state.clear()

    discount_note = None
    if discount_percent and base_amount and base_amount > amount_uah:
        discount_note = f"Скидка в честь открытия -{discount_percent:g}% уже применена (было {base_amount} грн)"

    receipt = format_order_receipt(
        order_num, now_kyiv().strftime("%d.%m.%Y %H:%M"), "Telegram Stars", f"{count} шт.",
        price_str, target, lang, discount_note=discount_note
    )
    await message.answer(receipt + loc.t("pay.choose_method", lang), reply_markup=kb.pay_method_kb(order_id, None, db.get_ref_stats(message.from_user.id)[1]))

# --- ПОКУПКА PREMIUM ---

@router.message(F.text.in_(loc.all_variants("menu.buy_premium")))
async def buy_premium_start(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    # Автоотмена: если уже в процессе покупки
    if await _cancel_if_in_buy_fsm(message, state, lang):
        return

    if await _antispam_check(message.from_user.id, message):
        return

    await message.answer(loc.t("prem.choose_period", lang), reply_markup=kb.premium_choice_kb())

@router.callback_query(F.data == "prem_login_support")
async def buy_premium_login_support(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await state.set_state(SupportState.active_chat)
    await callback.message.answer(loc.t("prem.login_info", lang), reply_markup=kb.close_support_kb())
    await callback.answer()

@router.callback_query(F.data.startswith("prem_"))
async def buy_premium_choice(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    choice = callback.data.split("_")[1]
    price_uah = float(db.get_setting(f"premium_{choice}"))
    price_str = get_multicurrency_string(price_uah)
    duration_map = {
        "3m": {"ru": "3 месяца", "en": "3 months", "ua": "3 місяці"},
        "6m": {"ru": "6 месяцев", "en": "6 months", "ua": "6 місяців"},
        "1y": {"ru": "1 год", "en": "1 year", "ua": "1 рік"},
    }
    duration = duration_map.get(choice, {}).get(lang, choice)
    
    await state.update_data(duration=duration, price_uah=price_uah, price_str=price_str)
    await callback.message.answer(
        f"Telegram Premium — {duration}\n{price_str}\n\n{loc.t('prem.enter_username', lang)}",
        reply_markup=kb.username_entry_kb(lang, callback.from_user.username)
    )
    await state.set_state(BuyPremium.get_username)
    await callback.answer()

@router.message(BuyPremium.get_username)
async def buy_premium_username(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    if message.text in kb.CANCEL_TEXTS:
        await state.clear()
        await message.answer("Отменено.", reply_markup=kb.main_menu(lang))
        return

    if message.text in loc.all_menu_variants():
        await state.clear()
        await message.answer("❌ Заказ отклонён — вы нажали другую кнопку во время оформления.", reply_markup=kb.main_menu(lang))
        return

    # Кнопка "Свой юзернейм"
    if message.text in kb.MY_USERNAME_TEXTS:
        if not message.from_user.username:
            await message.answer("❌ У вас не установлен юзернейм в Telegram. Введите юзернейм вручную.")
            return
        target = f"@{message.from_user.username}"
    else:
        target = message.text.strip()
    if not await validate_tg_username(target):
        await message.answer(loc.t("stars.bad_username", lang))
        return
        
    data = await state.get_data()
    order_id, order_num = db.create_order(message.from_user.id, "PREMIUM", data['duration'], data['price_uah'], target)
    await state.clear()
    
    receipt = format_order_receipt(order_num, now_kyiv().strftime("%d.%m.%Y %H:%M"), "Telegram Premium", data['duration'], data['price_str'], target, lang)
    await message.answer(receipt + loc.t("pay.choose_method", lang), reply_markup=kb.pay_method_kb(order_id, None, db.get_ref_stats(message.from_user.id)[1]))

# --- АВТООТМЕНА: если нажали кнопку меню пока идёт FSM-покупка ---

BUY_FSM_STATES = (
    BuyStars.get_count,
    BuyStars.get_username,
    BuyPremium.get_username,
)

@router.message(StateFilter(BuyStars.get_count, BuyStars.get_username, BuyPremium.get_username))
async def auto_cancel_on_menu_press(message: Message, state: FSMContext):
    """Если пользователь нажал кнопку меню во время FSM — заказ отклоняется."""
    # Пропускаем служебные тексты — пусть обрабатывают нижестоящие хендлеры
    if (message.text in kb.CANCEL_TEXTS or
            message.text in kb.MY_USERNAME_TEXTS or
            (message.text and (message.text.startswith("@") or message.text.isdigit()))):
        return
    # Только кнопки меню вызывают автоотмену
    if message.text not in loc.all_menu_variants():
        return
    lang = db.get_language(message.from_user.id)
    await state.clear()
    await message.answer(
        "❌ Заказ отклонён — вы нажали другую кнопку во время оформления.",
        reply_markup=kb.main_menu(lang)
    )

# --- ОПЛАТА ---

# --- ОПЛАТА С БАЛАНСА (реферальный баланс + пополнения) ---

@router.callback_query(F.data.startswith("balpay_"))
async def pay_with_balance(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    order = db.get_order(order_id)
    if not order or order[1] != callback.from_user.id:
        await callback.answer("🚫 Это не ваш заказ.", show_alert=True)
        return
    if not db.pay_order_from_balance(callback.from_user.id, order_id, order[4]):
        _, bal = db.get_ref_stats(callback.from_user.id)
        await callback.answer(f"Недостаточно средств на балансе ({bal:.2f} грн) или заказ уже оплачен.", show_alert=True)
        return
    await callback.answer("✅ Оплачено с баланса")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await send_user(callback.from_user.id, "bal_review", num=order[10])
    await notify_management(
        f"🟢 Оплата с баланса (бот) — нужно выполнить заказ\nЗаказ: {order[10]}\n"
        f"Товар: {order[2]} ({order[3]})\nПолучатель: {order[8]}\nСумма: {order[4]} грн (списано с баланса)\n"
        f"Клиент: @{callback.from_user.username} (ID: {callback.from_user.id})",
        reply_markup=kb.admin_balance_order_kb(order_id))

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    parts = callback.data.split("_")
    method, order_id = parts[1], int(parts[2])
    order = db.get_order(order_id)
    if not order: return
    
    lang = db.get_language(callback.from_user.id)
    db.update_order_status(order_id, "ОЖИДАНИЕ_ОПЛАТЫ")
    price_str = get_multicurrency_string(order[4])
    
    if method == "card" and not db.card_is_configured():
        db.update_order_status(order_id, "ОТКЛОНЕН")
        await callback.message.answer("⚠️ Оплата картой временно недоступна. Выберите CryptoBot или напишите в поддержку.")
        await callback.answer()
        return
    if method == "card":
        card_num = db.get_setting("card_number")
        card_name = db.get_setting("card_name")
        text = loc.t("pay.card_text", lang, price_str=price_str, card_num=card_num, card_name=card_name)
        await callback.message.answer(text, reply_markup=kb.i_paid_kb(order_id))
    else:
        order_num = order[10]
        amount_uah = order[4]
        usd_for_crypto = round(amount_uah * get_uah_to_usd(), 2)
        await callback.message.answer(loc.t("pay.crypto_wait", lang))
        invoice, error_msg = await create_cryptobot_invoice(usd_for_crypto, order_num)
        if invoice:
            pay_url = invoice["pay_url"]
            invoice_id = invoice["invoice_id"]
            # Привязываем инвойс к заказу в БД — иначе при проверке оплаты
            # нельзя достоверно убедиться, что оплачен именно ЭТОТ заказ
            # (см. verify_crypto_payment).
            db.set_order_crypto_invoice(order_id, invoice_id)
            text = loc.t("pay.crypto_text", lang, usd=usd_for_crypto, price_str=price_str)
            crypto_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=loc.t("pay.crypto_btn_pay", lang), url=pay_url)],
                [InlineKeyboardButton(text=loc.t("pay.crypto_btn_check", lang), callback_data=f"check_crypto_{invoice_id}_{order_id}")],
                [InlineKeyboardButton(text=loc.t("pay.crypto_btn_cancel", lang), callback_data=f"cancel_order_{order_id}")]
            ])
            await callback.message.answer(text, reply_markup=crypto_kb)
        else:
            await callback.message.answer(loc.t("pay.crypto_fail", lang, error=error_msg))
    await callback.answer()

@router.callback_query(F.data.startswith("check_crypto_"))
async def verify_crypto_payment(callback: CallbackQuery):
    parts = callback.data.split("_")
    invoice_id = int(parts[2])
    order_id = int(parts[3])
    lang = db.get_language(callback.from_user.id)

    order = db.get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return

    # Заказ должен принадлежать нажавшему кнопку пользователю.
    if order[1] != callback.from_user.id:
        await callback.answer("🚫 Это не ваш заказ.", show_alert=True)
        return

    # Заказ уже закрыт — повторная проверка не нужна (защита от повторных нажатий).
    if order[5] in ("ВЫПОЛНЕН", "НА_РАССМОТРЕНИИ"):
        await callback.answer("✅ Заказ уже оплачен.", show_alert=True)
        return

    # КРИТИЧНО: инвойс из callback_data должен совпадать с инвойсом,
    # который был выпущен именно для ЭТОГО заказа. Без этой проверки
    # можно было подставить invoice_id от чужого/своего оплаченного
    # дешёвого счёта и закрыть дорогой заказ бесплатно.
    if not order[11] or str(order[11]) != str(invoice_id):
        await callback.answer("❌ Этот счёт не относится к данному заказу.", show_alert=True)
        return

    invoice_status, error_msg = await safe_check_invoice(invoice_id)

    if invoice_status and invoice_status.get("status") == "paid":
        # Доп. проверка суммы — оплаченный инвойс должен покрывать сумму заказа.
        paid_amount = float(invoice_status.get("amount", 0) or 0)
        expected_usd = round(order[4] * get_uah_to_usd(), 2)
        if paid_amount + 0.01 < expected_usd:
            await callback.answer("❌ Оплаченная сумма меньше суммы заказа. Свяжитесь с поддержкой.", show_alert=True)
            return

        db.update_order_status(order_id, "НА_РАССМОТРЕНИИ")
        order = db.get_order(order_id)
        price_str = get_multicurrency_string(order[4])
        await callback.message.answer(loc.t("pay.verified", lang))
        try:
            user_lang = db.get_language(order[1])
            await bot.send_message(order[1], loc.t("order.paid_notify", user_lang, order_num=order[10]))
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)
        u = db.get_user(order[1])
        uname = (u["username"] if u else None) or "—"
        msg = (
            f"🔔 Оплата CryptoBot — заказ оплачен\n"
            f"Заказ: {order[10]}\nТовар: {order[2]} ({order[3]})\n"
            f"Получатель: {order[8]}\nСумма: {price_str}\n"
            f"Клиент: @{uname} (ID: {order[1]})\nСтатус: НА РАССМОТРЕНИИ"
        )
        await notify_management(msg, reply_markup=kb.admin_crypto_order_kb(order_id))
        await callback.answer("✅")
    else:
        detail = error_msg if error_msg else "Статус счета еще не 'paid'."
        await callback.answer(f"❌ {detail}", show_alert=True)

@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_user(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    lang = db.get_language(callback.from_user.id)
    order = db.get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден.", show_alert=True)
        return
    # Заказ может отменить только его владелец (или админ).
    if order[1] != callback.from_user.id and not is_admin(callback.from_user.id):
        await callback.answer("🚫 Это не ваш заказ.", show_alert=True)
        return
    if order[5] not in db.OPEN_STATUSES:
        await callback.answer("ℹ️ Заказ уже закрыт.", show_alert=True)
        return
    if db.is_paid_from_balance(order_id) and not is_admin(callback.from_user.id):
        await callback.answer("ℹ️ Заказ оплачен с баланса и уже на рассмотрении — для отмены напишите в поддержку.", show_alert=True)
        return
    db.update_order_status(order_id, "ОТКЛОНЕН")
    await callback.message.answer(loc.t("order.cancelled", lang, order_id=order_id), reply_markup=kb.main_menu(lang))
    await callback.answer()

# --- ЗАГРУЗКА ЧЕКОВ ---

@router.callback_query(F.data.startswith("confirm_paid_"))
async def choose_proof_type(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    lang = db.get_language(callback.from_user.id)
    await state.update_data(order_id=order_id)
    await callback.message.answer(loc.t("proof.choose", lang), reply_markup=kb.proof_type_selection_kb(order_id))
    await state.set_state(PaymentState.select_proof_type)
    await callback.answer()

@router.callback_query(F.data == "proof_photo", PaymentState.select_proof_type)
async def proof_photo_mode(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    data = await state.get_data()
    await callback.message.answer(loc.t("proof.send_photo", lang), reply_markup=kb.cancel_kb(lang))
    await state.set_state(PaymentState.upload_photo)
    await callback.answer()

@router.callback_query(F.data == "proof_pdf", PaymentState.select_proof_type)
async def proof_pdf_mode(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await callback.message.answer(loc.t("proof.send_pdf", lang), reply_markup=kb.cancel_kb(lang))
    await state.set_state(PaymentState.upload_pdf)
    await callback.answer()

@router.message(PaymentState.upload_photo)
async def save_photo_proof(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    if message.text in kb.CANCEL_TEXTS:
        await state.clear()
        await message.answer("Загрузка чека отменена.", reply_markup=kb.main_menu(lang))
        return

    if not message.photo:
        await message.answer("📸 Пожалуйста, отправьте фото (не файл).")
        return

    data = await state.get_data()
    order_id = data['order_id']
    file_id = message.photo[-1].file_id
    db.update_order_status(order_id, "НА_ПРОВЕРКЕ", proof_file_id=file_id, proof_type="PHOTO")
    await state.clear()
    await message.answer(loc.t("proof.accepted", lang), reply_markup=kb.main_menu(lang))
    order = db.get_order(order_id)
    price_str = get_multicurrency_string(order[4])
    msg = f"🔔 Новый платеж (фото)\nЗаказ: {order[10]}\nТовар: {order[2]} ({order[3]})\nСумма: {price_str}\nПолучатель: {order[8]}\nОтправитель: @{message.from_user.username} (ID: {message.from_user.id})"
    await notify_management(msg, proof_id=file_id, proof_type="PHOTO", reply_markup=kb.admin_decision_kb(order_id))

@router.message(PaymentState.upload_pdf)
async def save_pdf_proof(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)

    if message.text in kb.CANCEL_TEXTS:
        await state.clear()
        await message.answer("Загрузка чека отменена.", reply_markup=kb.main_menu(lang))
        return

    if not message.document:
        await message.answer("📄 Пожалуйста, отправьте PDF-файл документом.")
        return

    data = await state.get_data()
    order_id = data['order_id']
    file_id = message.document.file_id
    db.update_order_status(order_id, "НА_ПРОВЕРКЕ", proof_file_id=file_id, proof_type="PDF")
    await state.clear()
    await message.answer(loc.t("proof.accepted", lang), reply_markup=kb.main_menu(lang))
    order = db.get_order(order_id)
    price_str = get_multicurrency_string(order[4])
    msg = f"🔔 Новый платеж (PDF)\nЗаказ: {order[10]}\nТовар: {order[2]} ({order[3]})\nСумма: {price_str}\nПолучатель: {order[8]}\nОтправитель: @{message.from_user.username} (ID: {message.from_user.id})"
    await notify_management(msg, proof_id=file_id, proof_type="PDF", reply_markup=kb.admin_decision_kb(order_id))

# --- ПОДДЕРЖКА ---

@router.message(F.text.in_(loc.all_variants("menu.support")))
async def support_init(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if await _cancel_if_in_buy_fsm(message, state, lang): return
    await state.set_state(SupportState.active_chat)
    await message.answer(loc.t("support.enter", lang), reply_markup=kb.close_support_kb())

@router.callback_query(F.data == "close_ticket")
async def support_close_ticket(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await state.clear()
    await callback.message.answer(loc.t("support.exit", lang), reply_markup=kb.main_menu(lang))
    await callback.answer()

@router.message(SupportState.active_chat)
async def support_forward_to_admin(message: Message, state: FSMContext):
    if message.text in loc.all_menu_variants():
        lang = db.get_language(message.from_user.id)
        await state.clear()
        await message.answer(loc.t("support.exit", lang))
        return
    lang = db.get_language(message.from_user.id)
    await notify_management(
        f"🆘 Сообщение в поддержку\n"
        f"От: @{message.from_user.username} (ID: {message.from_user.id})\n\n"
        f"Текст:\n{message.text}\n\n"
        f"Для ответа скопируйте команду:\n"
        f"/reply {message.from_user.id} Ваш ответ"
    )
    await message.answer(loc.t("support.sent", lang), reply_markup=kb.close_support_kb())

# --- ПОДДЕРЖКА ПРОЕКТА (ДОНАТЫ) ---

@router.message(F.text.in_(loc.all_variants("menu.donate")))
async def donate_init(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    await _cancel_if_in_buy_fsm(message, state, lang)
    await message.answer(loc.t("donate.intro", lang), reply_markup=kb.donate_method_kb(lang))

@router.callback_query(F.data == "donate_cancel")
async def donate_cancel(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    current = await state.get_state()
    if current in (DonateState.get_stars_amount.state, DonateState.get_crypto_amount.state):
        await state.clear()
    await callback.message.answer(loc.t("donate.cancelled", lang), reply_markup=kb.main_menu(lang))
    await callback.answer()

@router.callback_query(F.data == "donate_method_stars")
async def donate_method_stars(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    await callback.message.answer(loc.t("donate.stars_choose", lang), reply_markup=kb.donate_stars_kb(lang))
    await callback.answer()

@router.callback_query(F.data == "donate_method_crypto")
async def donate_method_crypto(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    await callback.message.answer(loc.t("donate.crypto_choose", lang), reply_markup=kb.donate_crypto_kb(lang))
    await callback.answer()

async def _send_stars_donation_invoice(chat_id: int, amount: int, lang: str):
    title = loc.t("donate.stars_invoice_title", lang)
    description = loc.t("donate.stars_invoice_desc", lang, amount=amount, company=config.COMPANY_NAME)
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=f"donate_stars_{amount}",
        provider_token="",  # Для Telegram Stars provider_token всегда пустой
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=amount)],
    )

@router.callback_query(F.data.startswith("donate_stars_") & ~F.data.contains("custom"))
async def donate_stars_preset(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    amount_str = callback.data.replace("donate_stars_", "")
    if not amount_str.isdigit():
        await callback.answer()
        return
    await _send_stars_donation_invoice(callback.from_user.id, int(amount_str), lang)
    await callback.answer()

@router.callback_query(F.data == "donate_stars_custom")
async def donate_stars_custom(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await state.set_state(DonateState.get_stars_amount)
    await callback.message.answer(loc.t("donate.stars_custom_prompt", lang))
    await callback.answer()

@router.message(DonateState.get_stars_amount)
async def donate_stars_custom_amount(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if message.text in loc.all_menu_variants():
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 100000):
        await message.answer(loc.t("donate.stars_invalid", lang))
        return
    await state.clear()
    await _send_stars_donation_invoice(message.from_user.id, int(text), lang)

@router.callback_query(F.data.startswith("donate_crypto_") & ~F.data.contains("custom"))
async def donate_crypto_preset(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    amount_str = callback.data.replace("donate_crypto_", "")
    if not amount_str.isdigit():
        await callback.answer()
        return
    await callback.answer()
    await _create_and_send_crypto_donation(callback.message, callback.from_user.id, float(amount_str), lang)

@router.callback_query(F.data == "donate_crypto_custom")
async def donate_crypto_custom(callback: CallbackQuery, state: FSMContext):
    lang = db.get_language(callback.from_user.id)
    await state.set_state(DonateState.get_crypto_amount)
    await callback.message.answer(loc.t("donate.crypto_custom_prompt", lang))
    await callback.answer()

@router.message(DonateState.get_crypto_amount)
async def donate_crypto_custom_amount(message: Message, state: FSMContext):
    lang = db.get_language(message.from_user.id)
    if message.text in loc.all_menu_variants():
        await state.clear()
        return
    text = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(text)
    except ValueError:
        amount = -1
    if not (1 <= amount <= 10000):
        await message.answer(loc.t("donate.crypto_invalid", lang))
        return
    await state.clear()
    await _create_and_send_crypto_donation(message, message.from_user.id, round(amount, 2), lang)

async def _create_and_send_crypto_donation(message: Message, user_id: int, amount_usd: float, lang: str):
    processing = await message.answer(loc.t("donate.crypto_creating", lang))
    order_num = f"DONATE-{uuid.uuid4().hex[:8].upper()}"
    invoice, error_msg = await create_cryptobot_invoice(amount_usd, order_num)
    try:
        await processing.delete()
    except Exception:
        pass
    if not invoice:
        await message.answer(loc.t("donate.crypto_error", lang, error=error_msg))
        return
    invoice_id = invoice["invoice_id"]
    pay_url = invoice["pay_url"]
    db.add_donation(user_id, "crypto", amount_usd, "USD", "PENDING", external_id=invoice_id)
    await message.answer(
        loc.t("donate.crypto_invoice_ready", lang, amount=amount_usd),
        reply_markup=kb.donate_crypto_pay_kb(pay_url, invoice_id, lang)
    )

@router.callback_query(F.data.startswith("donate_check_"))
async def donate_crypto_check(callback: CallbackQuery):
    lang = db.get_language(callback.from_user.id)
    invoice_id = int(callback.data.replace("donate_check_", ""))

    # БАГ №3 (фикс): если донат уже был подтверждён раньше (CryptoBot
    # продолжает отдавать status="paid" на уже оплаченный инвойс), не
    # повторяем уведомление админу — просто вежливо отвечаем пользователю
    # и убираем кнопку, чтобы больше не провоцировать повторные нажатия.
    existing = db.get_donation_by_external_id(invoice_id)
    if existing and existing["status"] == "PAID":
        await callback.answer("✅ Оплата уже подтверждена, спасибо ещё раз!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)
        return

    invoice_status, error_msg = await safe_check_invoice(invoice_id)
    if invoice_status and invoice_status.get("status") == "paid":
        db.mark_donation_paid(invoice_id)
        row = db.get_donation_by_external_id(invoice_id)
        amount = row["amount"] if row else invoice_status.get("amount")
        await callback.message.answer(loc.t("donate.crypto_thanks", lang, amount=amount), reply_markup=kb.main_menu(lang))
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)
        await notify_management(
            loc.t(
                "notify.new_donation_crypto", "ru",
                username=callback.from_user.username or "—",
                tg_id=callback.from_user.id,
                amount=amount,
            )
        )
    else:
        await callback.message.answer(loc.t("donate.crypto_not_paid", lang))
    await callback.answer()

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    lang = db.get_language(message.from_user.id)
    payload = payment.invoice_payload or ""
    if payload.startswith("donate_stars_"):
        amount = payment.total_amount  # для XTR total_amount уже равен количеству Stars
        db.add_donation(message.from_user.id, "stars", amount, "XTR", "PAID", external_id=payment.telegram_payment_charge_id)
        await message.answer(loc.t("donate.stars_thanks", lang, amount=amount), reply_markup=kb.main_menu(lang))
        await notify_management(
            loc.t(
                "notify.new_donation_stars", "ru",
                username=message.from_user.username or "—",
                tg_id=message.from_user.id,
                amount=amount,
            )
        )

# --- WEB APP (МАГАЗИН) ---

@router.message(F.web_app_data)
async def handle_shop_webapp_data(message: Message):
    """Обрабатывает данные, присланные мини-приложением магазина через tg.sendData()."""
    lang = db.get_language(message.from_user.id)
    raw_data = message.web_app_data.data
    logger.info(f"WebApp data от {message.from_user.id}: {raw_data}")
    await notify_management(
        f"🛍 Данные из веб-магазина\n"
        f"От: @{message.from_user.username} (ID: {message.from_user.id})\n\n"
        f"Данные:\n{raw_data}"
    )
    await message.answer(
        {
            "ru": "✅ Спасибо! Ваш запрос из магазина получен, мы скоро с вами свяжемся.",
            "en": "✅ Thanks! Your request from the shop was received, we'll be in touch shortly.",
            "ua": "✅ Дякуємо! Ваш запит з магазину отримано, ми скоро з вами зв'яжемося.",
        }.get(lang, "✅ Спасибо! Ваш запрос из магазина получен, мы скоро с вами свяжемся."),
        reply_markup=kb.main_menu(lang)
    )

# ============== ADMIN HANDLERS ==============

@router.message(F.reply_to_message, StateFilter("*"))
@admin_only
async def admin_native_reply(message: Message):
    if not message.text: return
    reply = message.reply_to_message
    text_to_search = reply.text or reply.caption or ""
    match = re.search(r"\(ID:\s*(\d+)\)", text_to_search)
    if match:
        target_uid = int(match.group(1))
        try:
            user_lang = db.get_language(target_uid)
            await bot.send_message(
                chat_id=target_uid,
                text=loc.t("notify.support_reply", user_lang, text=html.escape(message.text)),
                parse_mode="HTML",
                reply_markup=kb.close_support_kb()
            )
            await message.answer(f"✅ Ответ успешно доставлен пользователю {target_uid}.")
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки: {e}")

@router.message(Command("admin"), StateFilter("*"))
@admin_only
async def cmd_admin(message: Message):
    await message.answer("Панель управления StarlifyShop", reply_markup=kb.admin_menu_kb())

@router.message(Command("reply"), StateFilter("*"))
@admin_only
async def cmd_reply_support(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Синтаксис: /reply ID_ЮЗЕРА Текст ответа")
        return
    if not parts[1].isdigit():
        await message.answer("❌ ID_ЮЗЕРА должен быть числом.")
        return
    target_uid = int(parts[1])
    reply_text = parts[2]
    try:
        user_lang = db.get_language(target_uid)
        await bot.send_message(
            chat_id=target_uid,
            text=loc.t("notify.support_reply", user_lang, text=html.escape(reply_text)),
            parse_mode="HTML",
            reply_markup=kb.close_support_kb()
        )
        await message.answer(f"✅ Ответ доставлен пользователю {target_uid}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

@router.message(Command("create"), StateFilter("*"))
@admin_only
async def admin_create_test_payment(message: Message):
    """Тестовый платёж CryptoBot для админа: /create <сумма> <актив>.

    Пример: /create 0.00001 USDT
    Создаёт РЕАЛЬНЫЙ инвойс в Crypto Pay на указанную сумму в указанной
    криптовалюте (без конвертации через фиат) — удобно, чтобы быстро
    проверить, что токен CryptoBot и вся цепочка "создать -> оплатить ->
    проверить" работают, не создавая при этом заказ в магазине.
    """
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer(
            "🧪 Тестовый платёж CryptoBot\n\n"
            "Использование: /create <сумма> <актив>\n"
            "Например: /create 0.00001 USDT\n\n"
            f"Доступные активы: {', '.join(SUPPORTED_CRYPTO_ASSETS)}"
        )
        return

    _, amount_str, asset_raw = parts
    asset = asset_raw.strip().upper()
    amount_str = amount_str.strip().replace(",", ".")

    try:
        amount_value = float(amount_str)
    except ValueError:
        await message.answer("❌ Некорректная сумма. Пример: /create 0.00001 USDT")
        return

    if amount_value <= 0:
        await message.answer("❌ Сумма должна быть больше нуля.")
        return

    if asset not in SUPPORTED_CRYPTO_ASSETS:
        await message.answer(
            f"❌ Неподдерживаемый актив: {asset}\n"
            f"Доступные активы: {', '.join(SUPPORTED_CRYPTO_ASSETS)}"
        )
        return

    wait_msg = await message.answer(f"⏳ Создаю тестовый счёт на {amount_str} {asset}...")

    invoice, error_msg = await create_cryptobot_crypto_invoice(
        amount_str, asset, f"Тестовый платёж администратора (ID {message.from_user.id})"
    )

    if not invoice:
        await wait_msg.edit_text(
            f"❌ Не удалось создать тестовый счёт.\n\nПричина: {error_msg}\n\n"
            "Проверьте CRYPTO_BOT_TOKEN в .env и доступность pay.crypt.bot."
        )
        return

    invoice_id = invoice["invoice_id"]
    pay_url = invoice.get("bot_invoice_url") or invoice.get("pay_url")

    test_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_test_{invoice_id}")],
    ])

    await wait_msg.edit_text(
        "✅ Тестовый счёт создан\n"
        f"ID инвойса: {invoice_id}\n"
        f"Сумма: {amount_str} {asset}\n"
        f"Статус: активен (ожидает оплаты)\n\n"
        "ℹ️ Это технический тестовый платёж для проверки интеграции CryptoBot. "
        "Он НЕ создаёт заказ в магазине и не влияет на статистику продаж.",
        reply_markup=test_kb
    )

@router.callback_query(F.data.startswith("check_test_"), StateFilter("*"))
async def admin_check_test_payment(callback: CallbackQuery):
    """Проверка статуса тестового инвойса, созданного через /create."""
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Недоступно.", show_alert=True)
        return

    try:
        invoice_id = int(callback.data.replace("check_test_", ""))
    except ValueError:
        await callback.answer("❌ Некорректный ID счёта.", show_alert=True)
        return

    invoice_status, error_msg = await safe_check_invoice(invoice_id)

    if invoice_status is None:
        await callback.answer(f"❌ {error_msg}", show_alert=True)
        return

    status = invoice_status.get("status")
    amount = invoice_status.get("amount")
    asset = invoice_status.get("asset")

    if status == "paid":
        try:
            base_text = callback.message.text or callback.message.caption or ""
            if "✅ ОПЛАЧЕН" not in base_text:
                await callback.message.edit_text(base_text + f"\n\n✅ ОПЛАЧЕН — {amount} {asset}")
        except Exception:
            logger.warning("Не удалось обновить сообщение тестового счёта", exc_info=True)
        await callback.answer("✅ Счёт оплачен! Интеграция CryptoBot работает корректно.", show_alert=True)
    elif status == "expired":
        await callback.answer("⌛ Счёт истёк, оплата не поступила вовремя.", show_alert=True)
    else:
        await callback.answer("ℹ️ Счёт пока не оплачен.", show_alert=True)

@router.message(Command("order"), StateFilter("*"))
@admin_only
async def cmd_order_active(message: Message):
    """Просмотр активных заказов для админа."""
    active = db.get_active_orders()
    if not active:
        await message.answer("✅ Активных (незакрытых) заказов нет.")
        return
    
    text = f"📋 Активные заказы ({len(active)} шт.):\n\n"
    for o in active[:20]:
        oid, uid, uname, itype, details, amount, status, target, date, order_num = o
        uname_str = f"@{uname}" if uname else str(uid)
        text += (
            f"🔹 {order_num}\n"
            f"   Клиент: {uname_str} (ID: {uid})\n"
            f"   Товар: {itype} [{details}]\n"
            f"   Сумма: {amount} грн\n"
            f"   Статус: {loc.order_status_label(status)}\n"
            f"   Получатель: {target}\n"
            f"   Дата: {date}\n"
            f"   /accept {order_num}\n"
            f"   ————————————\n"
        )
    if len(active) > 20:
        text += f"\n…и ещё {len(active) - 20} заказов."
    await message.answer(text)

@router.callback_query(F.data == "admin_active_orders", StateFilter("*"))
@admin_only
async def admin_active_orders_btn(callback: CallbackQuery):
    active = db.get_active_orders()
    if not active:
        await callback.message.answer("✅ Активных заказов нет.")
        await callback.answer()
        return
    
    text = f"📋 Активные заказы ({len(active)} шт.):\n\n"
    for o in active[:15]:
        oid, uid, uname, itype, details, amount, status, target, date, order_num = o
        uname_str = f"@{uname}" if uname else str(uid)
        text += (
            f"🔹 {order_num} | {loc.order_status_label(status)}\n"
            f"   {uname_str} → {itype} [{details}] — {amount} грн\n"
            f"   /accept {order_num}\n\n"
        )
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data.startswith("adm_"), StateFilter("*"))
@admin_only
async def admin_immediate_decision(callback: CallbackQuery):
    parts = callback.data.split("_")
    action, order_id = parts[1], int(parts[2])
    order = db.get_order(order_id)
    if not order: return
    uid = order[1]
    user_lang = db.get_language(uid)
    if action == "review":
        db.update_order_status(order_id, "НА_РАССМОТРЕНИИ")
        await callback.message.answer(f"Заказ {order[10]} переведен в режим рассмотрения.")
        try:
            await bot.send_message(uid, loc.t("notify.review", user_lang))
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)
    elif action == "done":
        if order[5] == "ВЫПОЛНЕН":
            await callback.answer("ℹ️ Заказ уже выполнен.", show_alert=True)
            return
        if order[5] == "ОТКЛОНЕН":
            await callback.answer("ℹ️ Заказ уже отклонён.", show_alert=True)
            return
        db.update_order_status(order_id, "ВЫПОЛНЕН")
        await callback.message.answer(f"✅ Заказ {order[10]} закрыт как выполненный.")
        await send_receipt(order, uid)
    elif action == "reject":
        was_open = order[5] in db.OPEN_STATUSES
        refunded = was_open and db.is_paid_from_balance(order_id)
        db.update_order_status(order_id, "ОТКЛОНЕН")
        if refunded:
            await callback.message.answer(f"Заказ {order[10]} отклонен, {order[4]} грн возвращены клиенту на баланс.")
        else:
            await callback.message.answer(f"Заказ {order[10]} отклонен.")
        try:
            if refunded:
                await send_user(uid, "bal_refund", amount=order[4])
            else:
                await bot.send_message(uid, loc.t("notify.rejected", user_lang))
        except Exception:
            logger.warning("Второстепенное действие не выполнено (уведомление/сообщение)", exc_info=True)
    await callback.answer()

@router.message(Command("accept"), StateFilter("*"))
@admin_only
async def admin_accept_order(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Формат команды: /accept НомерЗаказа")
        return
    order_num = parts[1]
    order = db.get_order_by_num(order_num)
    if not order:
        await message.answer("Заказ с таким номером не найден в базе данных.")
        return
    # БАГ №1 (фикс): предупреждаем админа о повторном подтверждении.
    # Само повторное начисление бонусов теперь исключено на уровне
    # database.update_order_status, но лучше не давать админу молча
    # закрыть уже закрытый заказ второй раз.
    if order[5] == "ВЫПОЛНЕН":
        await message.answer(f"ℹ️ Заказ {order_num} уже был отмечен как выполненный ранее. Повторное начисление бонусов не производится.")
        return
    db.update_order_status(order[0], "ВЫПОЛНЕН")
    await message.answer(f"✅ Заказ {order_num} закрыт как выполненный.")
    await send_receipt(order, order[1])

@router.callback_query(F.data == "admin_settings", StateFilter("*"))
@admin_only
async def admin_settings_hub(callback: CallbackQuery):
    await callback.message.answer("Параметры для изменения:", reply_markup=kb.admin_settings_list())
    await callback.answer()

@router.callback_query(F.data == "admin_back_to_menu", StateFilter("*"))
@admin_only
async def admin_back_to_menu(callback: CallbackQuery):
    await callback.message.answer("Панель управления StarlifyShop", reply_markup=kb.admin_menu_kb())
    await callback.answer()

def _discount_status_text(enabled: bool, percent: float) -> str:
    status = "🟢 ВКЛЮЧЕНА" if enabled else "🔴 выключена"
    text_preview = get_stars_discount_text(percent)
    body = (
        f"🎉 Скидка в честь открытия (на покупку звёзд)\n\n"
        f"Статус: {status}\n"
        f"Размер скидки: {percent:g}%\n"
        f"Текст скидки: {text_preview}\n\n"
        f"Пока скидка включена, она автоматически применяется в каталоге, "
        f"при оформлении заказа и в чеке покупателя."
    )
    return body

@router.callback_query(F.data == "admin_discount_hub", StateFilter("*"))
@admin_only
async def admin_discount_hub(callback: CallbackQuery):
    enabled = db.get_setting("stars_discount_enabled") == "1"
    percent = float(db.get_setting("stars_discount_percent") or 0)
    await callback.message.answer(_discount_status_text(enabled, percent), reply_markup=kb.admin_discount_kb(enabled, percent))
    await callback.answer()

@router.callback_query(F.data == "discount_toggle", StateFilter("*"))
@admin_only
async def admin_discount_toggle(callback: CallbackQuery):
    enabled = db.get_setting("stars_discount_enabled") == "1"
    new_enabled = not enabled
    db.set_setting("stars_discount_enabled", "1" if new_enabled else "0")
    percent = float(db.get_setting("stars_discount_percent") or 0)
    await callback.message.answer(
        _discount_status_text(new_enabled, percent),
        reply_markup=kb.admin_discount_kb(new_enabled, percent)
    )
    await callback.answer("🎉 Скидка включена!" if new_enabled else "Скидка выключена")

@router.callback_query(F.data.startswith("set_"), StateFilter("*"))
@admin_only
async def admin_edit_setting_value(callback: CallbackQuery, state: FSMContext):
    key = callback.data[4:]
    val = db.get_setting(key)
    await state.update_data(target_key=key)
    if key == "stars_discount_text":
        await callback.message.answer(
            f"Текущий текст скидки:\n{val}\n\n"
            f"Введите новый текст. Можно использовать {{percent}} — он автоматически "
            f"заменится на текущий процент скидки (например: {get_stars_discount_percent():g})."
        )
    else:
        hints = {
            "usd_rate": "Курс доллара: сколько грн за 1 $ (например 41.7). По нему считаются крипто-счета.",
            "ton_rate": "Курс TON: сколько грн за 1 TON (например 290). Введите 0 — тогда курс берётся из CryptoBot автоматически.",
            "stars_min": "Минимальное количество звёзд в одном заказе (целое число, например 50).",
            "stars_rate": "Цена 1 звезды в грн (например 0.77).",
        }
        hint = hints.get(key, "")
        await callback.message.answer(
            f"Текущее значение {key}: {val}\n\n" + (hint + "\n\n" if hint else "") + "Введите новое значение:")
    await state.set_state(AdminSettings.change_value)
    await callback.answer()


# Настройки, которые обязаны быть положительным числом — если админ ошибётся
# и введёт нечисловое значение, бот упадёт при следующей покупке (float(...) в
# buy_stars_start / buy_premium_choice). Проверяем это на входе.
NUMERIC_SETTINGS = {
    "stars_rate", "premium_3m", "premium_6m", "premium_1y",
    "referral_bonus_percent", "stars_discount_percent",
    "usd_rate", "ton_rate", "stars_min",
}
# Допускают 0: для ton_rate 0 = «брать курс из CryptoBot автоматически».
ZERO_OK_SETTINGS = {"ton_rate"}
# Только целые числа.
INT_SETTINGS = {"stars_min"}
# Проценты допускают 0 (в отличие от цен/курса, которые обязаны быть > 0) и не могут быть больше 100.
PERCENT_SETTINGS = {"referral_bonus_percent", "stars_discount_percent"}

@router.message(AdminSettings.change_value)
@admin_only
async def admin_save_setting_value(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data['target_key']
    new_val = message.text.strip()

    if key in NUMERIC_SETTINGS:
        normalized = new_val.replace(",", ".").replace("%", "")
        try:
            value = float(normalized)
            if key in PERCENT_SETTINGS:
                if not (0 <= value <= 100):
                    raise ValueError
            elif key in ZERO_OK_SETTINGS:
                if value < 0:
                    raise ValueError
            elif value <= 0:
                raise ValueError
            if key in INT_SETTINGS:
                if value != int(value):
                    raise ValueError
                value = int(value)
        except ValueError:
            if key in PERCENT_SETTINGS:
                err = f"❌ Параметр {key} должен быть числом от 0 до 100 (например: 20)."
            else:
                err = (f"❌ Параметр {key} должен быть целым положительным числом (например: 50)." if key in INT_SETTINGS
                       else f"❌ Параметр {key} должен быть положительным числом (например: 0.77).")
            await message.answer(f"{err}\nПопробуйте ещё раз или нажмите /admin для отмены.")
            return
        new_val = str(value)

    db.set_setting(key, new_val)
    await state.clear()

    if key == "stars_discount_percent":
        enabled = db.get_setting("stars_discount_enabled") == "1"
        await message.answer(
            f"✅ Процент скидки обновлён → {new_val}%",
            reply_markup=kb.admin_discount_kb(enabled, float(new_val))
        )
    elif key == "stars_discount_text":
        enabled = db.get_setting("stars_discount_enabled") == "1"
        percent = float(db.get_setting("stars_discount_percent") or 0)
        preview = get_stars_discount_text(percent)
        await message.answer(
            f"✅ Текст скидки обновлён. Превью:\n\n{preview}",
            reply_markup=kb.admin_discount_kb(enabled, percent)
        )
    else:
        shown = new_val
        if key == "ton_rate" and float(new_val) == 0:
            shown = "0 (авто из CryptoBot)"
        await message.answer(f"✅ Параметр {key} обновлен → {shown}")

@router.callback_query(F.data == "admin_broadcast", StateFilter("*"))
@admin_only
async def admin_broadcast_init(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте сообщение для глобальной рассылки:")
    await state.set_state(AdminBroadcast.get_content)
    await callback.answer()

@router.message(AdminBroadcast.get_content)
@admin_only
async def admin_broadcast_execute(message: Message, state: FSMContext):
    await state.clear()
    users = db.get_all_users()
    await message.answer("Рассылка запущена...")
    good, bad = 0, 0
    for u in users:
        try:
            if message.photo:
                await bot.send_photo(chat_id=u, photo=message.photo[-1].file_id, caption=message.caption)
            else:
                await bot.send_message(chat_id=u, text=message.text)
            good += 1
        except Exception:
            bad += 1
        await asyncio.sleep(0.04)
    await message.answer(f"Рассылка завершена\nДоставлено: {good}\nНе доставлено: {bad}")

@router.callback_query(F.data == "admin_stats", StateFilter("*"))
@admin_only
async def admin_statistics_view(callback: CallbackQuery):
    total_users, total_orders, sold_stars, sold_premium, revenue, active_users = db.get_stats_db()
    active_orders = db.get_active_orders()
    donate_stars_total, donate_crypto_total, donors_count = db.get_donations_stats()
    text = (
        f"📊 Сводная статистика:\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🛍 Количество покупателей: {active_users}\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"🔴 Активных (незакрытых): {len(active_orders)}\n"
        f"⭐ Продано звезд: {sold_stars}\n"
        f"💎 Продано Premium: {sold_premium}\n"
        f"💰 Общий оборот: {revenue} грн\n\n"
        f"💖 Донаты:\n"
        f"  • ⭐ Stars получено: {donate_stars_total}\n"
        f"  • 🪙 Крипто получено: {donate_crypto_total} $\n"
        f"  • 🙋 Уникальных донатеров: {donors_count}"
    )
    await callback.message.answer(text)
    await callback.answer()



# ============== ПОПОЛНЕНИЯ / ВЫВОДЫ / РАЗДЕЛЫ (админ) ==============
USER_MSGS = {
    "topup_ok": {"ru": "✅ Баланс пополнен на {amount} грн. Теперь им можно оплачивать заказы в магазине.",
                 "ua": "✅ Баланс поповнено на {amount} грн. Тепер ним можна оплачувати замовлення в магазині.",
                 "en": "✅ Your balance was topped up by {amount} UAH. You can now pay for orders with it."},
    "topup_no": {"ru": "❌ Пополнение на {amount} грн отклонено. Если вы оплатили — напишите в поддержку.",
                 "ua": "❌ Поповнення на {amount} грн відхилено. Якщо ви оплатили — напишіть у підтримку.",
                 "en": "❌ Your top-up of {amount} UAH was declined. If you paid, please contact support."},
    "bal_review": {"ru": "🕓 Заказ {num} оплачен с баланса и передан на рассмотрение. Мы сообщим, когда он будет выполнен.",
                   "ua": "🕓 Замовлення {num} оплачено з балансу й передано на розгляд. Ми повідомимо, коли його буде виконано.",
                   "en": "🕓 Order {num} was paid from your balance and is now under review. We'll let you know once it's completed."},
    "bal_refund": {"ru": "↩️ Заказ отклонён, {amount} грн возвращены на ваш баланс.",
                   "ua": "↩️ Замовлення відхилено, {amount} грн повернуто на ваш баланс.",
                   "en": "↩️ Your order was rejected; {amount} UAH has been returned to your balance."},
    "wd_ok":    {"ru": "✅ Вывод {amount} грн выполнен.",
                 "ua": "✅ Виведення {amount} грн виконано.",
                 "en": "✅ Your withdrawal of {amount} UAH has been paid."},
    "wd_no":    {"ru": "❌ Вывод {amount} грн отклонён, сумма возвращена на баланс.",
                 "ua": "❌ Виведення {amount} грн відхилено, суму повернуто на баланс.",
                 "en": "❌ Your withdrawal of {amount} UAH was declined; the amount is back on your balance."},
}


async def send_user(user_id: int, key: str, **vars):
    try:
        lang = db.get_language(user_id)
        text = USER_MSGS[key].get(lang) or USER_MSGS[key]["ru"]
        await bot.send_message(user_id, text.format(**vars))
    except Exception:
        logger.warning("Не удалось отправить сообщение клиенту", exc_info=True)


async def _finish_admin_msg(callback: CallbackQuery, suffix: str):
    try:
        await callback.message.edit_text((callback.message.text or "") + "\n\n" + suffix, reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("topup_ok_"))
async def topup_ok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Только для админа", show_alert=True)
        return
    tid = int(callback.data.split("_")[2])
    if not db.topup_transition(tid, ("ОЖИДАНИЕ", "НА_ПРОВЕРКЕ"), "ЗАЧИСЛЕНО"):
        await callback.answer("Уже обработано", show_alert=True)
        await _finish_admin_msg(callback, "ℹ️ Уже обработано")
        return
    tp = db.get_topup(tid)
    db.credit_balance(tp["user_id"], tp["amount"])
    await send_user(tp["user_id"], "topup_ok", amount=tp["amount"])
    await _finish_admin_msg(callback, f"✅ Зачислено {tp['amount']} грн ({callback.from_user.full_name})")
    await callback.answer("Зачислено")


@router.callback_query(F.data.startswith("topup_no_"))
async def topup_no(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Только для админа", show_alert=True)
        return
    tid = int(callback.data.split("_")[2])
    if not db.topup_transition(tid, ("ОЖИДАНИЕ", "НА_ПРОВЕРКЕ"), "ОТКЛОНЕНО"):
        await callback.answer("Уже обработано", show_alert=True)
        await _finish_admin_msg(callback, "ℹ️ Уже обработано")
        return
    tp = db.get_topup(tid)
    await send_user(tp["user_id"], "topup_no", amount=tp["amount"])
    await _finish_admin_msg(callback, f"❌ Отклонено ({callback.from_user.full_name})")
    await callback.answer("Отклонено")


@router.callback_query(F.data.startswith("wd_ok_"))
async def withdraw_ok(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Только для админа", show_alert=True)
        return
    wid = int(callback.data.split("_")[2])
    if not db.withdrawal_transition(wid, "ОЖИДАНИЕ", "ВЫПЛАЧЕНО"):
        await callback.answer("Уже обработано", show_alert=True)
        await _finish_admin_msg(callback, "ℹ️ Уже обработано")
        return
    wd = db.get_withdrawal(wid)
    await send_user(wd["user_id"], "wd_ok", amount=wd["amount"])
    await _finish_admin_msg(callback, f"✅ Выплачено ({callback.from_user.full_name})")
    await callback.answer("Готово")


@router.callback_query(F.data.startswith("wd_no_"))
async def withdraw_no(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🚫 Только для админа", show_alert=True)
        return
    wid = int(callback.data.split("_")[2])
    if not db.withdrawal_transition(wid, "ОЖИДАНИЕ", "ОТКЛОНЕНО"):
        await callback.answer("Уже обработано", show_alert=True)
        await _finish_admin_msg(callback, "ℹ️ Уже обработано")
        return
    wd = db.get_withdrawal(wid)
    db.credit_balance(wd["user_id"], wd["amount"])
    await send_user(wd["user_id"], "wd_no", amount=wd["amount"])
    await _finish_admin_msg(callback, f"❌ Отклонено, сумма возвращена ({callback.from_user.full_name})")
    await callback.answer("Возвращено на баланс")


@router.message(Command("credit"), StateFilter("*"))
async def cmd_credit(message: Message, command: CommandObject):
    """/credit ID_клиента сумма — ручное зачисление на баланс (отрицательная сумма — списание)."""
    if not is_admin(message.from_user.id):
        return
    try:
        uid_s, amount_s = (command.args or "").split()
        uid, amount = int(uid_s), round(float(amount_s.replace(",", ".")), 2)
    except ValueError:
        await message.answer("Формат: /credit ID сумма   (например: /credit 123456789 300)")
        return
    if not db.get_user(uid):
        await message.answer("❌ Клиент с таким ID не найден.")
        return
    if amount >= 0:
        db.credit_balance(uid, amount)
    elif not db.debit_balance(uid, -amount):
        await message.answer("❌ На балансе клиента недостаточно средств.")
        return
    await message.answer(f"✅ Готово. Баланс клиента {uid} изменён на {amount} грн.")


SECTION_TITLES = {"stars": "TG Stars", "premium": "TG Premium", "ton": "Курс TON", "nft": "NFT",
                  "reviews": "Отзывы", "channel": "Наш ТГК", "support": "Поддержка"}


def _sections_text() -> str:
    hidden = set(db.get_hidden_sections())
    lines = [f"{'🚫 скрыт ' if k in hidden else '✅ виден  '} {k} — {SECTION_TITLES[k]}" for k in db.SECTION_KEYS]
    return ("Разделы Mini App:\n" + "\n".join(lines) +
            "\n\nСкрыть: /hide nft\nПоказать: /show nft\nНесколько сразу: /hide nft ton reviews")


@router.message(Command("sections"), StateFilter("*"))
async def cmd_sections(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(_sections_text())


@router.message(Command("hide"), StateFilter("*"))
async def cmd_hide(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    keys = [k.lower() for k in (command.args or "").replace(",", " ").split() if k.lower() in db.SECTION_KEYS]
    if not keys:
        await message.answer(_sections_text())
        return
    db.set_hidden_sections(list(db.get_hidden_sections()) + keys)
    await message.answer("✅ Скрыто.\n\n" + _sections_text())


@router.message(Command("show"), StateFilter("*"))
async def cmd_show(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    keys = [k.lower() for k in (command.args or "").replace(",", " ").split() if k.lower() in db.SECTION_KEYS]
    if not keys:
        await message.answer(_sections_text())
        return
    db.set_hidden_sections([k for k in db.get_hidden_sections() if k not in keys])
    await message.answer("✅ Показано.\n\n" + _sections_text())

# ============== АВТОНОМНОСТЬ: уведомления, бэкап, keep-alive ==============
async def notify_user_paid(order):
    """Сообщает клиенту, что заказ оплачен (используется фоновой проверкой оплаты)."""
    try:
        user_lang = db.get_language(order["user_id"])
        await bot.send_message(order["user_id"], loc.t("order.paid_notify", user_lang, order_num=order["order_num"]))
    except Exception:
        logger.warning("Не удалось уведомить клиента об оплате", exc_info=True)


def _make_db_snapshot() -> str:
    """Консистентная копия базы (работает и с WAL). Возвращает путь к временному файлу."""
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    src = sqlite3.connect(config.DB_PATH)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return tmp


async def send_backup_to_admins(reason: str = "авто"):
    from aiogram.types import FSInputFile
    try:
        tmp = await asyncio.to_thread(_make_db_snapshot)
    except Exception:
        logger.exception("Не удалось сделать копию базы")
        return
    try:
        name = f"starlify_backup_{now_kyiv():%Y%m%d_%H%M}.db"
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_document(
                    admin_id, FSInputFile(tmp, filename=name),
                    caption=f"💾 Копия базы ({reason}). Чтобы восстановить — отправьте этот файл боту с подписью /restore")
            except Exception:
                logger.warning("Не удалось отправить бэкап админу %s", admin_id, exc_info=True)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


async def backup_loop():
    if config.BACKUP_HOURS <= 0:
        return
    await asyncio.sleep(120)
    while True:
        await send_backup_to_admins()
        await asyncio.sleep(config.BACKUP_HOURS * 3600)


async def keepalive_loop():
    """Бесплатные хостинги усыпляют приложение без входящих запросов — пингуем сами себя."""
    url = config.SHOP_WEBAPP_URL.rstrip("/") + "/api/health"
    await asyncio.sleep(60)
    while True:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
                async with s.get(url) as r:
                    await r.read()
        except Exception:
            logger.debug("keepalive: пинг не прошёл", exc_info=True)
        await asyncio.sleep(600)


@router.message(F.document, F.caption.startswith("/restore"), StateFilter("*"))
async def restore_db(message: Message):
    """Админ присылает файл базы с подписью /restore — база заменяется (нужно после перезапуска
    бесплатного хостинга без постоянного диска)."""
    if not is_admin(message.from_user.id):
        return
    if message.document.file_size and message.document.file_size > 40 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой.")
        return
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        await bot.download(message.document, destination=tmp)
        check = sqlite3.connect(tmp)
        try:
            tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"users", "orders"} <= tables:
                await message.answer("❌ Это не база StarlifyShop (нет таблиц users/orders).")
                return
            src_conn, dst_conn = check, sqlite3.connect(config.DB_PATH)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            check.close()
        db.init_db()
        db.apply_env_settings()
        await message.answer("✅ База восстановлена.")
    except Exception as e:
        logger.exception("restore_db")
        await message.answer(f"❌ Не удалось восстановить: {e}")
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass

# --- ЗАПУСК ---
async def main():
    db.init_db()
    db.apply_env_settings()
    sub_mw = SubscriptionMiddleware()
    dp.message.outer_middleware(sub_mw)
    dp.callback_query.outer_middleware(sub_mw)
    dp.message.middleware(AntiFloodMiddleware())
    dp.callback_query.middleware(AntiFloodMiddleware())
    dp.include_router(router)
    me = await bot.get_me()
    await premium_emoji.load(bot)
    background_tasks = []
    if config.WEBAPI_ENABLED:
        watcher = await webapi.start({
            "bot_username": me.username,
            "notify_user_paid": notify_user_paid,
            "UAH_TO_USD": UAH_TO_USD, "UAH_TO_TON": UAH_TO_TON,
            "get_uah_to_usd": get_uah_to_usd, "get_ton_uah_manual": get_ton_uah_manual,
            "get_stars_min": get_stars_min,
            "cryptobot_request": _cryptobot_request,
            "create_cryptobot_invoice": create_cryptobot_invoice,
            "safe_check_invoice": safe_check_invoice,
            "notify_management": notify_management,
            "validate_tg_username": validate_tg_username,
            "get_stars_discount_percent": get_stars_discount_percent,
            "apply_stars_discount": apply_stars_discount,
            "admin_decision_kb": kb.admin_decision_kb,
            "admin_balance_kb": kb.admin_balance_order_kb, "admin_crypto_kb": kb.admin_crypto_order_kb,
            "topup_kb": kb.topup_decision_kb,
            "withdraw_kb": kb.withdraw_decision_kb,
            "send_user": send_user,
        })
        background_tasks.append(watcher)
    background_tasks.append(asyncio.create_task(backup_loop()))
    if config.KEEPALIVE and config.SHOP_WEBAPP_URL:
        background_tasks.append(asyncio.create_task(keepalive_loop()))
    # Синяя кнопка меню рядом со строкой ввода — открывает магазин (настраивать в BotFather не нужно)
    if config.SHOP_WEBAPP_URL.startswith("https://"):
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🛍 Магазин", web_app=WebAppInfo(url=config.SHOP_WEBAPP_URL)))
        except Exception as e:
            logging.warning(f"Не удалось поставить кнопку меню: {e}")
    else:
        logging.warning("SHOP_WEBAPP_URL не задан (нужен https://) — кнопка Mini App не будет показана.")
    logging.info("Система StarlifyShop запущена.")
    if not db.card_is_configured():
        await notify_management("⚠️ Реквизиты карты не заданы — оплата и пополнение картой отключены.\n"
                                "Задайте переменные CARD_NUMBER и CARD_NAME в настройках хостинга "
                                "(или кнопками в /admin) — и перезапустите бота.")
    for attempt in range(5):
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            break
        except TelegramServerError as e:
            logging.warning(f"Telegram временно недоступен (попытка {attempt + 1}/5): {e}")
            await asyncio.sleep(5)
    else:
        logging.error("Не удалось связаться с Telegram после 5 попыток.")
    while True:
        try:
            await dp.start_polling(bot)
            break
        except TelegramServerError as e:
            logging.warning(f"Сбой соединения: {e}. Перезапуск через 5 сек...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
