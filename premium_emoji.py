"""Премиум-эмодзи для бота без переписывания текстов.

Как работает:
1. На старте бот загружает твой пак (PREMIUM_EMOJI_PACK) и строит таблицу
   «обычный эмодзи -> custom_emoji_id» по полю `emoji` каждого стикера пака.
2. Middleware перехватывает ВСЕ исходящие запросы (send_message, edit_message_text,
   send_photo с caption и т.д.) и подменяет обычные эмодзи в тексте на премиум.
3. (Опционально, PREMIUM_BUTTONS=1) то же для инлайн-кнопок: эмодзи в начале
   текста кнопки убирается и ставится как icon_custom_emoji_id.
4. (Опционально, PREMIUM_MENU=1) то же для нижнего меню (reply-клавиатура). Когда эмодзи
   убран из текста кнопки, Telegram присылает при нажатии текст БЕЗ эмодзи, поэтому
   InboundMiddleware возвращает ему исходный вид, и все хендлеры по тексту работают как раньше.

Ручная правка таблицы: файл premium_emoji_map.json рядом с ботом, формат
{"⭐": "5368324170671202286", "❌": "..."} - он перекрывает автоматику.
Чтобы отключить подмену конкретного эмодзи: {"💰": null}.

Требование Telegram: премиум-эмодзи от бота работают, если у ВЛАДЕЛЬЦА бота есть
Telegram Premium (или у бота куплен доп. юзернейм на Fragment). Зрителям Premium не нужен.
"""
import json
import logging
import os
import re

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram import BaseMiddleware
from aiogram.types import (
    InlineKeyboardMarkup, KeyboardButton, MessageEntity, ReplyKeyboardMarkup,
)

logger = logging.getLogger("starlify.premium_emoji")

PACK_NAME = os.getenv("PREMIUM_EMOJI_PACK", "StarlifyStars")  # можно несколько паков через запятую: "Pack1,Pack2"
PACK_NAMES = [n.strip() for n in PACK_NAME.split(",") if n.strip()]
ENABLED = os.getenv("PREMIUM_EMOJI", "1").lower() in ("1", "true", "yes")
BUTTONS_ENABLED = os.getenv("PREMIUM_BUTTONS", "1").lower() in ("1", "true", "yes")
MENU_ENABLED = os.getenv("PREMIUM_MENU", "1").lower() in ("1", "true", "yes")
MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "premium_emoji_map.json")

VS16 = "\ufe0f"

_emoji_map: dict[str, str] = {}   # эмодзи без VS16 -> custom_emoji_id
_pattern: re.Pattern | None = None
_menu_originals: dict[str, str] = {}   # текст без эмодзи -> исходный текст кнопки меню


def _norm(e: str) -> str:
    return e.replace(VS16, "")


def _rebuild_pattern():
    global _pattern
    if not _emoji_map:
        _pattern = None
        return
    keys = sorted(_emoji_map, key=len, reverse=True)
    _pattern = re.compile(
        "|".join("".join(re.escape(c) + VS16 + "?" for c in k) for k in keys)
    )


async def load(bot) -> int:
    """Загружает пак и ручные переопределения. Возвращает число эмодзи в таблице."""
    _emoji_map.clear()
    if not ENABLED:
        logger.info("Премиум-эмодзи отключены (PREMIUM_EMOJI=0).")
        return 0
    for name in PACK_NAMES:   # первый пак важнее: его иконки не перезаписываются следующими
        try:
            pack = await bot.get_sticker_set(name)
            for s in pack.stickers:
                if s.custom_emoji_id and s.emoji:
                    # если у нескольких стикеров одинаковый эмодзи — берём первый
                    _emoji_map.setdefault(_norm(s.emoji), s.custom_emoji_id)
        except Exception as e:
            logger.warning("Не удалось загрузить пак %r: %s", name, e)
    if os.path.exists(MAP_FILE):
        try:
            with open(MAP_FILE, encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    if v:
                        _emoji_map[_norm(k)] = str(v)
                    else:
                        _emoji_map.pop(_norm(k), None)
        except Exception as e:
            logger.warning("Ошибка чтения %s: %s", MAP_FILE, e)
    _rebuild_pattern()
    _prefill_menu_originals()
    logger.info("Премиум-эмодзи: в таблице %d шт. (паки: %s)", len(_emoji_map), ", ".join(PACK_NAMES))
    return len(_emoji_map)


def _split_leading(text: str):
    """(эмодзи_в_начале, остаток) или None, если в начале нет эмодзи из таблицы."""
    if not _pattern or not text:
        return None
    m = _pattern.match(text)
    if not m or not _id_for(m.group()):
        return None
    rest = text[m.end():].lstrip()
    return (m.group(), rest) if rest else None


def _prefill_menu_originals():
    """Заранее запоминаем «без эмодзи -> с эмодзи» для всех строк бота,
    чтобы нажатия на старые клавиатуры после перезапуска тоже работали."""
    _menu_originals.clear()
    if not (MENU_ENABLED and _pattern):
        return
    candidates: set[str] = set()
    try:
        import locales
        for entry in locales.STRINGS.values():
            if isinstance(entry, dict):
                candidates.update(v for v in entry.values() if isinstance(v, str))
    except Exception:
        logger.warning("Не удалось прочитать locales для меню", exc_info=True)
    try:
        import keyboards
        for name in ("CANCEL_TEXTS", "MY_USERNAME_TEXTS"):
            candidates.update(getattr(keyboards, name, ()))
    except Exception:
        logger.warning("Не удалось прочитать keyboards для меню", exc_info=True)
    for t in candidates:
        sp = _split_leading(t)
        if sp:
            _menu_originals.setdefault(sp[1], t)


def _id_for(match_text: str) -> str | None:
    return _emoji_map.get(_norm(match_text))


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _to_entities(text: str, existing):
    """Обычный текст -> список entities (текст не меняется, длины не сдвигаются)."""
    new = []
    protected = [e for e in (existing or []) if e.type in ("code", "pre")]
    for m in _pattern.finditer(text):
        eid = _id_for(m.group())
        if not eid:
            continue
        off = _utf16_len(text[:m.start()])
        ln = _utf16_len(m.group())
        if any(p.offset <= off < p.offset + p.length for p in protected):
            continue
        new.append(MessageEntity(type="custom_emoji", offset=off, length=ln, custom_emoji_id=eid))
    if not new:
        return None
    allent = list(existing or []) + new
    allent.sort(key=lambda e: e.offset)
    return allent


_TAG_RE = re.compile(r"(<[^>]*>)")


def _to_html(text: str) -> str:
    """HTML-текст: оборачиваем эмодзи в <tg-emoji>, не трогая теги, <code> и <pre>."""
    out, depth_code = [], 0
    for part in _TAG_RE.split(text):
        if part.startswith("<") and part.endswith(">"):
            low = part.lower()
            if low.startswith(("<code", "<pre")):
                depth_code += 1
            elif low.startswith(("</code", "</pre")):
                depth_code = max(0, depth_code - 1)
            out.append(part)
            continue
        if depth_code:
            out.append(part)
            continue
        out.append(_pattern.sub(
            lambda m: f'<tg-emoji emoji-id="{_id_for(m.group())}">{m.group()}</tg-emoji>'
            if _id_for(m.group()) else m.group(),
            part,
        ))
    return "".join(out)


def _convert_buttons(markup: InlineKeyboardMarkup):
    rows, changed = [], False
    for row in markup.inline_keyboard:
        new_row = []
        for b in row:
            m = _pattern.match(b.text or "")
            eid = _id_for(m.group()) if m else None
            if eid and not b.icon_custom_emoji_id:
                rest = b.text[m.end():].lstrip()
                if rest:  # кнопка только из эмодзи остаётся как есть
                    b = b.model_copy(update={"text": rest, "icon_custom_emoji_id": eid})
                    changed = True
            new_row.append(b)
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows) if changed else None


def _convert_reply_menu(markup: ReplyKeyboardMarkup):
    rows, changed = [], False
    for row in markup.keyboard:
        new_row = []
        for b in row:
            if isinstance(b, KeyboardButton) and not b.icon_custom_emoji_id:
                sp = _split_leading(b.text or "")
                if sp:
                    _menu_originals.setdefault(sp[1], b.text)
                    b = b.model_copy(update={"text": sp[1], "icon_custom_emoji_id": _id_for(sp[0])})
                    changed = True
            new_row.append(b)
        rows.append(new_row)
    return markup.model_copy(update={"keyboard": rows}) if changed else None


# метод -> (поле текста, поле entities)
_TEXT_FIELDS = {
    "SendMessage": ("text", "entities"),
    "EditMessageText": ("text", "entities"),
    "SendPhoto": ("caption", "caption_entities"),
    "SendDocument": ("caption", "caption_entities"),
    "SendVideo": ("caption", "caption_entities"),
    "SendAnimation": ("caption", "caption_entities"),
    "SendAudio": ("caption", "caption_entities"),
    "SendVoice": ("caption", "caption_entities"),
    "EditMessageCaption": ("caption", "caption_entities"),
}


class PremiumEmojiMiddleware(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        if not _pattern:
            return await make_request(bot, method)

        saved = {}

        def change(attr, value):
            saved.setdefault(attr, getattr(method, attr, None))
            setattr(method, attr, value)

        try:
            fields = _TEXT_FIELDS.get(type(method).__name__)
            if fields:
                tf, ef = fields
                text = getattr(method, tf, None)
                if isinstance(text, str) and text:
                    pm = getattr(method, "parse_mode", None)
                    if not isinstance(pm, str):  # Default(...) -> берём значение по умолчанию бота
                        pm = getattr(getattr(bot, "default", None), "parse_mode", None)
                    pm = getattr(pm, "value", pm)
                    if pm is None:
                        ents = _to_entities(text, getattr(method, ef, None))
                        if ents:
                            change(ef, ents)
                            change("parse_mode", None)
                    elif str(pm).upper() == "HTML":
                        new_text = _to_html(text)
                        if new_text != text:
                            change(tf, new_text)
                    # Markdown/MarkdownV2 не трогаем

            rm = getattr(method, "reply_markup", None)
            new_rm = None
            if BUTTONS_ENABLED and isinstance(rm, InlineKeyboardMarkup):
                new_rm = _convert_buttons(rm)
            elif MENU_ENABLED and isinstance(rm, ReplyKeyboardMarkup):
                new_rm = _convert_reply_menu(rm)
            if new_rm:
                change("reply_markup", new_rm)
        except Exception:
            logger.exception("Ошибка подмены эмодзи, отправляю как есть")
            for a, v in saved.items():
                setattr(method, a, v)
            saved.clear()

        if not saved:
            return await make_request(bot, method)
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as e:
            # Telegram отклонил премиум-эмодзи (нет Premium у владельца и т.п.) — шлём обычные
            low = str(e).lower()
            if not any(w in low for w in ("emoji", "entit", "icon", "button")):
                raise
            logger.warning("Премиум-эмодзи отклонены (%s), повтор с обычными.", e)
            for a, v in saved.items():
                setattr(method, a, v)
            return await make_request(bot, method)


class InboundMiddleware(BaseMiddleware):
    """Возвращает тексту нажатой кнопки меню исходный вид (с эмодзи), чтобы работали
    все хендлеры вида F.text.in_(...) и проверки message.text in CANCEL_TEXTS."""

    async def __call__(self, handler, event, data):
        text = getattr(event, "text", None)
        if _menu_originals and text:
            orig = _menu_originals.get(text)
            if orig and orig != text:
                event = event.model_copy(update={"text": orig})
        return await handler(event, data)


def install(bot, dp=None):
    """Подключить middleware к боту (вызвать один раз после создания Bot и Dispatcher)."""
    bot.session.middleware(PremiumEmojiMiddleware())
    if dp is not None:
        dp.message.outer_middleware(InboundMiddleware())
