"""
HTTP API для Mini App магазина (запускается в том же процессе, что и бот).

Главный принцип: КЛИЕНТУ НЕ ВЕРИМ. Всё, что влияет на деньги, делает сервер:
  * пользователь определяется по подписи Telegram initData (HMAC), а не по словам клиента;
  * цену заказа считает сервер по настройкам из БД;
  * счёт CryptoBot создаёт сервер и привязывает к заказу;
  * «Проверить оплату» спрашивает CryptoBot напрямую по привязанному счёту —
    заказ закрывается только если счёт реально `paid` и сумма покрывает заказ.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from urllib.parse import parse_qsl, urlparse

from aiohttp import web

import config
import database as db

logger = logging.getLogger("starlify.webapi")

D: dict = {}                       # зависимости из main.py (см. start())
_lock = asyncio.Lock()             # защита от двойного закрытия заказа параллельными проверками
_last_check: dict[int, float] = {}
_rates = {"ts": 0.0, "ton_uah": None, "usd_uah": None}

PREMIUM_LABELS = {"3m": "3 месяца", "6m": "6 месяцев", "1y": "1 год"}


# ---------------- безопасность ----------------
def verify_init_data(init_data: str, max_age: int = 86400):
    """Проверяет подпись Telegram WebApp initData. Возвращает dict пользователя или None."""
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        their_hash = parsed.pop("hash", None)
        if not their_hash:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
        ours = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(ours, their_hash):
            return None
        if time.time() - int(parsed.get("auth_date", 0)) > max_age:
            return None
        user = json.loads(parsed["user"])
        return user if isinstance(user.get("id"), int) else None
    except Exception:
        return None


def _allowed_origin() -> str:
    if getattr(config, "WEBAPI_ALLOWED_ORIGIN", ""):
        return config.WEBAPI_ALLOWED_ORIGIN
    if not config.SHOP_WEBAPP_URL:
        return ""   # сайт и API на одном адресе — CORS не нужен
    u = urlparse(config.SHOP_WEBAPP_URL)
    return f"{u.scheme}://{u.netloc}"


@web.middleware
async def cors_mw(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as e:
            resp = e
    origin = _allowed_origin()
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data, ngrok-skip-browser-warning"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Vary"] = "Origin"
    return resp


def err(msg: str, status: int = 400):
    return web.json_response({"error": msg}, status=status)


def authed(handler):
    async def wrapper(request):
        user = verify_init_data(request.headers.get("X-Telegram-Init-Data", ""))
        if not user:
            return err("Откройте магазин через Telegram", 401)
        db.add_user(user["id"], user.get("username"))
        return await handler(request, user)
    return wrapper


# ---------------- курсы / цены ----------------
async def get_rates():
    # Курс доллара всегда задаёт админ (usd_rate) — по нему же считаются крипто-счета.
    usd_uah = 1 / D["get_uah_to_usd"]()
    # Курс TON: ручной из админки; если там 0 — живой из CryptoBot (запасной — константа).
    manual_ton = D["get_ton_uah_manual"]()
    if manual_ton:
        return manual_ton, usd_uah
    if _rates["ton_uah"] and time.time() - _rates["ts"] < 300:
        return _rates["ton_uah"], usd_uah
    ton_uah = 1 / D["UAH_TO_TON"]
    res, _ = await D["cryptobot_request"]("GET", "getExchangeRates")
    for r in (res or []):
        if r.get("is_valid") and r.get("target") == "UAH" and r.get("source") == "TON":
            ton_uah = float(r["rate"])
    _rates.update(ts=time.time(), ton_uah=ton_uah)
    return ton_uah, usd_uah


def calc_price(product, count, plan):
    """Цена и описание товара — только по данным сервера."""
    if product == "stars":
        min_stars = D["get_stars_min"]()
        if not isinstance(count, int) or isinstance(count, bool) or not min_stars <= count <= 100000:
            raise ValueError(f"Минимальное количество — {min_stars} звёзд")
        base = round(count * float(db.get_setting("stars_rate")), 2)
        return D["apply_stars_discount"](base, D["get_stars_discount_percent"]()), "STARS", str(count)
    if product == "premium" and plan in PREMIUM_LABELS:
        return float(db.get_setting(f"premium_{plan}")), "PREMIUM", PREMIUM_LABELS[plan]
    raise ValueError("Неверный товар")


# ---------------- handlers ----------------
@authed
async def profile(request, user):
    uid = user["id"]
    u = db.get_user(uid)
    ref_count, ref_balance = db.get_ref_stats(uid)
    ton_uah, usd_uah = await get_rates()
    discount = D["get_stars_discount_percent"]()
    orders = [
        {"num": o["order_num"], "product": o["item_type"].lower(), "count": o["details"],
         "label": (o["details"] + " Stars") if o["item_type"] == "STARS" else "Premium — " + o["details"],
         "amount": o["amount"], "status": o["status"], "date": o["date"], "target": ""}
        for o in db.get_user_orders(uid)[:50]
    ]
    return web.json_response({
        "balance_uah": round(ref_balance, 2), "ref_bonus": db.get_ref_bonus(uid), "ref_count": ref_count, "ref_earned": round(db.get_ref_earned(uid), 2),
        "referral_percent": float(db.get_setting("referral_bonus_percent") or 5),
        "reg_date": (u["reg_date"] or "").split(" ")[0] if u else "",
        "stars_rate": float(db.get_setting("stars_rate")), "discount_percent": discount,
        "discount_text": ((db.get_setting("stars_discount_text") or "").replace("{percent}", str(int(discount) if float(discount).is_integer() else discount)) if discount else ""),
        "stars_min": D["get_stars_min"](),
        "premium": {k: float(db.get_setting(f"premium_{k}")) for k in PREMIUM_LABELS},
        "ton_uah": round(ton_uah, 2), "usd_uah": round(usd_uah, 2),
        "orders": orders,
        "hidden_sections": db.get_hidden_sections(),
    })


@authed
async def create_order(request, user):
    uid = user["id"]
    try:
        body = await request.json()
        amount, item_type, details = calc_price(body.get("product"), body.get("count"), body.get("premium_plan"))
    except ValueError as e:
        return err(str(e))
    except Exception:
        return err("Некорректный запрос")

    if body.get("who") == "custom":
        target = str(body.get("target", "")).strip()
    else:
        if not user.get("username"):
            return err("У вас не установлен юзернейм в Telegram — введите его вручную")
        target = user["username"]
    target = "@" + target.replace("https://t.me/", "").lstrip("@")
    if not await D["validate_tg_username"](target):
        return err("Введите корректный юзернейм получателя")

    open_o = db.get_open_order(uid)
    if open_o:
        return err(f"У вас уже есть незакрытый заказ {open_o['order_num']}. Завершите или отмените его.", 409)

    method = body.get("pay_method")
    if method not in ("crypto", "card", "balance"):
        return err("Неверный способ оплаты")
    if method == "card" and not db.card_is_configured():
        return err("Оплата картой временно недоступна, выберите CryptoBot или напишите в поддержку", 503)

    order_id, order_num = db.create_order(uid, item_type, details, amount, target)

    if method == "balance":
        # Деньги списываются и заказ уходит «НА_РАССМОТРЕНИИ» одной транзакцией.
        # Выполняет заказ админ (кнопка «Выполнен» или /accept), при отклонении деньги вернутся.
        if not db.pay_order_from_balance(uid, order_id, amount):
            db.update_order_status(order_id, "ОТКЛОНЕН")
            return err("Недостаточно средств на балансе")
        await D["notify_management"](
            f"🟢 Оплата с баланса (Mini App) — нужно выполнить заказ\nЗаказ: {order_num}\n"
            f"Товар: {item_type} ({details})\nПолучатель: {target}\nСумма: {amount} грн (списано с баланса)\n"
            f"Статус: НА РАССМОТРЕНИИ\nКлиент: @{user.get('username')} (ID: {uid})",
            reply_markup=D["admin_balance_kb"](order_id))
        await D["send_user"](uid, "bal_review", num=order_num)
        return web.json_response({"order_num": order_num, "amount_uah": amount,
                                  "status": "НА_РАССМОТРЕНИИ", "paid": False, "on_review": True})

    db.update_order_status(order_id, "ОЖИДАНИЕ_ОПЛАТЫ")
    resp = {"order_num": order_num, "amount_uah": amount, "status": "ОЖИДАНИЕ_ОПЛАТЫ"}

    if method == "crypto":
        usd = round(amount * D["get_uah_to_usd"](), 2)
        invoice, error = await D["create_cryptobot_invoice"](usd, order_num)
        if not invoice:
            logger.warning("CryptoBot invoice failed: %s", error)
            db.update_order_status(order_id, "ОТКЛОНЕН")
            return err("Не удалось создать счёт CryptoBot, попробуйте позже", 502)
        db.set_order_crypto_invoice(order_id, invoice["invoice_id"])
        resp["pay_url"] = invoice["pay_url"]
    else:
        resp["card"] = {"number": db.get_setting("card_number"), "name": db.get_setting("card_name")}
    return web.json_response(resp)


def _own_order(request, user):
    o = db.get_order_by_num(request.match_info["num"])
    return o if o and o["user_id"] == user["id"] else None


@authed
async def check_order(request, user):
    o = _own_order(request, user)
    if not o:
        return err("Заказ не найден", 404)
    async with _lock:
        o = db.get_order(o["id"])                       # свежий статус внутри блокировки
        if o["status"] == "ВЫПОЛНЕН":
            return web.json_response({"status": "paid"})
        if o["status"] not in db.OPEN_STATUSES:
            return web.json_response({"status": "closed"})
        if not o["crypto_invoice_id"]:
            return web.json_response({"status": "pending"})
        now = time.time()
        if now - _last_check.get(user["id"], 0) < 2:
            return web.json_response({"status": "pending"})
        _last_check[user["id"]] = now

        invoice, error = await D["safe_check_invoice"](int(o["crypto_invoice_id"]))
        if not invoice:
            logger.warning("check invoice failed: %s", error)
            return err("Не удалось проверить оплату, попробуйте ещё раз", 502)
        status = invoice.get("status")
        if status == "expired":
            return web.json_response({"status": "expired"})
        if status != "paid":
            return web.json_response({"status": "pending"})

        expected = round(o["amount"] * D["get_uah_to_usd"](), 2)
        if float(invoice.get("amount", 0) or 0) + 0.01 < expected:
            await D["notify_management"](f"⚠️ Недоплата по заказу {o['order_num']} (ожидалось {expected}$)")
            return web.json_response({"status": "underpaid"})

        db.update_order_status(o["id"], "ВЫПОЛНЕН")
    await D["notify_management"](
        f"🟢 Авто-оплата CryptoBot (Mini App)\nЗаказ: {o['order_num']}\n"
        f"Товар: {o['item_type']} ({o['details']})\nПолучатель: {o['username_target']}\n"
        f"Сумма: {o['amount']} грн → ВЫПОЛНЕН"
    )
    return web.json_response({"status": "paid"})


@authed
async def order_proof(request, user):
    o = _own_order(request, user)
    if not o:
        return err("Заказ не найден", 404)
    if o["status"] != "ОЖИДАНИЕ_ОПЛАТЫ" or o["crypto_invoice_id"]:
        return err("Для этого заказа чек не нужен", 409)
    try:
        comment = str((await request.json()).get("comment", ""))[:500]
    except Exception:
        comment = ""
    db.update_order_status(o["id"], "НА_ПРОВЕРКЕ")
    await D["notify_management"](
        f"🔔 Оплата картой (Mini App) — чек НЕ прикреплён\nЗаказ: {o['order_num']}\n"
        f"Товар: {o['item_type']} ({o['details']})\nСумма: {o['amount']} грн\nПолучатель: {o['username_target']}\n"
        f"Клиент: @{user.get('username')} (ID: {user['id']})\nКомментарий: {comment or '—'}\n\n"
        f"Проверьте поступление на карту, при необходимости запросите чек у клиента.",
        reply_markup=D["admin_decision_kb"](o["id"]),
    )
    return web.json_response({"status": "review"})


@authed
async def cancel_order(request, user):
    o = _own_order(request, user)
    if not o:
        return err("Заказ не найден", 404)
    if o["status"] in ("НОВЫЙ", "ОЖИДАНИЕ_ОПЛАТЫ"):
        db.update_order_status(o["id"], "ОТКЛОНЕН")
    return web.json_response({"ok": True})


async def _notify_request(user, title, text):
    await D["notify_management"](f"{title}\nОт: @{user.get('username')} (ID: {user['id']})\n\n{text}")


@authed
async def support_message(request, user):
    text = str((await request.json()).get("text", "")).strip()[:1000]
    if not text:
        return err("Пустое сообщение")
    await _notify_request(user, "💬 Сообщение из Mini App (ответ: /reply ID текст)", text)
    return web.json_response({"ok": True})


TOPUP_MIN, TOPUP_MAX = 10.0, 100000.0


async def _credit_topup(topup_id, source="") -> bool:
    """Зачисляет пополнение ровно один раз (атомарный переход статуса)."""
    if not db.topup_transition(topup_id, ("ОЖИДАНИЕ", "НА_ПРОВЕРКЕ"), "ЗАЧИСЛЕНО"):
        return False
    tp = db.get_topup(topup_id)
    db.credit_balance(tp["user_id"], tp["amount"])
    await D["send_user"](tp["user_id"], "topup_ok", amount=tp["amount"])
    if source:
        await D["notify_management"](f"🟢 Пополнение #{topup_id} зачислено ({source})\n"
                                     f"Клиент ID: {tp['user_id']}\nСумма: {tp['amount']} грн")
    return True


@authed
async def topup(request, user):
    uid = user["id"]
    try:
        b = await request.json()
        amount = round(float(b.get("amount_uah")), 2)
    except Exception:
        return err("Введите сумму")
    method = b.get("method")
    if not TOPUP_MIN <= amount <= TOPUP_MAX:
        return err(f"Сумма пополнения: от {int(TOPUP_MIN)} до {int(TOPUP_MAX)} грн")
    if method not in ("card", "crypto"):
        return err("Неверный способ пополнения")
    if method == "card" and not db.card_is_configured():
        return err("Пополнение картой временно недоступно, выберите CryptoBot", 503)
    if db.count_open_topups(uid) >= 3:
        return err("У вас уже есть несколько незавершённых пополнений. Дождитесь их обработки.", 409)

    topup_id = db.create_topup(uid, amount, method)
    resp = {"topup_id": topup_id, "amount_uah": amount, "method": method}
    if method == "crypto":
        usd = round(amount * D["get_uah_to_usd"](), 2)
        invoice, error = await D["create_cryptobot_invoice"](usd, f"TOPUP-{topup_id}")
        if not invoice:
            logger.warning("CryptoBot topup invoice failed: %s", error)
            db.topup_transition(topup_id, ("ОЖИДАНИЕ",), "ОТКЛОНЕНО")
            return err("Не удалось создать счёт CryptoBot, попробуйте позже", 502)
        db.set_topup_invoice(topup_id, invoice["invoice_id"])
        resp["pay_url"] = invoice["pay_url"]
    else:
        resp["card"] = {"number": db.get_setting("card_number"), "name": db.get_setting("card_name")}
    return web.json_response(resp)


def _own_topup(request, user):
    try:
        tp = db.get_topup(int(request.match_info["id"]))
    except (ValueError, TypeError):
        return None
    return tp if tp and tp["user_id"] == user["id"] else None


@authed
async def topup_paid(request, user):
    """Клиент нажал «Я оплатил» (карта) — админу уходит заявка с кнопками «Зачислить / Отклонить»."""
    tp = _own_topup(request, user)
    if not tp:
        return err("Пополнение не найдено", 404)
    if tp["method"] != "card" or not db.topup_transition(tp["id"], ("ОЖИДАНИЕ",), "НА_ПРОВЕРКЕ"):
        return err("Пополнение уже обработано", 409)
    await D["notify_management"](
        f"➕ Заявка на пополнение #{tp['id']} (карта)\n"
        f"Клиент: @{user.get('username')} (ID: {user['id']})\nСумма: {tp['amount']} грн\n\n"
        f"Проверьте поступление на карту и нажмите кнопку.",
        reply_markup=D["topup_kb"](tp["id"]))
    return web.json_response({"status": "review"})


@authed
async def topup_check(request, user):
    tp = _own_topup(request, user)
    if not tp:
        return err("Пополнение не найдено", 404)
    if tp["status"] == "ЗАЧИСЛЕНО":
        return web.json_response({"status": "paid"})
    if tp["status"] != "ОЖИДАНИЕ" or tp["method"] != "crypto" or not tp["invoice_id"]:
        return web.json_response({"status": "pending"})
    async with _lock:
        invoice, error = await D["safe_check_invoice"](int(tp["invoice_id"]))
        if not invoice:
            return err("Не удалось проверить оплату, попробуйте ещё раз", 502)
        if invoice.get("status") == "expired":
            db.topup_transition(tp["id"], ("ОЖИДАНИЕ",), "ОТКЛОНЕНО")
            return web.json_response({"status": "expired"})
        if invoice.get("status") != "paid":
            return web.json_response({"status": "pending"})
        if float(invoice.get("amount", 0) or 0) + 0.01 < round(tp["amount"] * D["get_uah_to_usd"](), 2):
            return web.json_response({"status": "underpaid"})
        await _credit_topup(tp["id"], "CryptoBot")
    return web.json_response({"status": "paid"})


@authed
async def ref_transfer(request, user):
    """Реферальный баланс -> основной баланс (мгновенно, без админа)."""
    amount = db.transfer_ref_bonus(user["id"])
    if amount <= 0:
        return err("Нет реферальных бонусов для перевода")
    return web.json_response({"ok": True, "amount": amount})


@authed
async def withdraw(request, user):
    try:
        b = await request.json()
        amount = round(float(b.get("amount_uah")), 2)
    except Exception:
        return err("Введите сумму")
    req = str(b.get("requisites", "")).strip()[:200]
    if amount <= 0:
        return err("Введите сумму")
    if not req:
        return err("Укажите реквизиты")
    wd_id = db.create_withdrawal(user["id"], amount, req)      # сумма сразу резервируется
    if wd_id is None:
        return err("Сумма превышает баланс")
    await D["notify_management"](
        f"➖ Заявка на вывод #{wd_id}\nКлиент: @{user.get('username')} (ID: {user['id']})\n"
        f"Сумма: {amount} грн (уже списана с баланса клиента)\nРеквизиты: {req}\n\n"
        f"Переведите деньги и нажмите «Выплачено». «Отклонить» вернёт сумму на баланс.",
        reply_markup=D["withdraw_kb"](wd_id))
    return web.json_response({"ok": True})


async def payment_watcher():
    """Фоновая проверка: если клиент оплатил счёт CryptoBot, но не нажал «Проверить оплату»,
    заказ всё равно закроется сам, а клиент и админ получат уведомление."""
    await asyncio.sleep(10)
    while True:
        try:
            for row in db.get_pending_crypto_orders():
                async with _lock:
                    o = db.get_order(row["id"])
                    if not o or o["status"] != "ОЖИДАНИЕ_ОПЛАТЫ" or not o["crypto_invoice_id"]:
                        continue
                    invoice, _error = await D["safe_check_invoice"](int(o["crypto_invoice_id"]))
                    if not invoice or invoice.get("status") != "paid":
                        continue
                    expected = round(o["amount"] * D["get_uah_to_usd"](), 2)
                    if float(invoice.get("amount", 0) or 0) + 0.01 < expected:
                        continue          # недоплата — оставляем как есть, разберётся админ
                    db.update_order_status(o["id"], "ВЫПОЛНЕН")
                await D["notify_user_paid"](o)
                await D["notify_management"](
                    f"🟢 Авто-оплата CryptoBot (фоновая проверка)\nЗаказ: {o['order_num']}\n"
                    f"Товар: {o['item_type']} ({o['details']})\nПолучатель: {o['username_target']}\n"
                    f"Сумма: {o['amount']} грн → ВЫПОЛНЕН"
                )
                await asyncio.sleep(0.5)
            for tp in db.get_pending_crypto_topups():
                async with _lock:
                    cur = db.get_topup(tp["id"])
                    if not cur or cur["status"] != "ОЖИДАНИЕ":
                        continue
                    invoice, _error = await D["safe_check_invoice"](int(cur["invoice_id"]))
                    if not invoice:
                        continue
                    if invoice.get("status") == "expired":
                        db.topup_transition(cur["id"], ("ОЖИДАНИЕ",), "ОТКЛОНЕНО")
                        continue
                    if invoice.get("status") != "paid":
                        continue
                    if float(invoice.get("amount", 0) or 0) + 0.01 < round(cur["amount"] * D["get_uah_to_usd"](), 2):
                        continue
                    await _credit_topup(cur["id"], "CryptoBot, фоновая проверка")
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("payment_watcher: ошибка итерации")
        await asyncio.sleep(max(15, config.PAYMENT_WATCH_SECONDS))



TG_SHIM = """<script>
/* Запасной вариант: если telegram-web-app.js не загрузился (блокировка сети и т.п.),
   берём данные запуска прямо из адреса, который Telegram передаёт мини-аппу. */
(function(){
  var diag = "script=" + (window.Telegram && window.Telegram.WebApp ? 1 : 0);
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) { window.__tgdiag = diag + " data=1"; return; }
  var data = "";
  try { data = new URLSearchParams(location.hash.replace(/^#/, "")).get("tgWebAppData") || ""; } catch(e){}
  if (!data) { try { var st = JSON.parse(sessionStorage.getItem("__telegram__initParams") || "{}"); data = st.tgWebAppData || ""; } catch(e){} }
  diag += " hash=" + (data ? 1 : 0);
  window.__tgdiag = diag;
  if (!data || (window.Telegram && window.Telegram.WebApp)) { return; }
  var user = null;
  try { user = JSON.parse(new URLSearchParams(data).get("user")); } catch(e){}
  var noop = function(){};
  var stub = function(){ return new Proxy(noop, { get: function(_, k){ return k === "onClick" ? noop : stub(); }, apply: noop }); };
  var app = new Proxy({ initData: data, initDataUnsafe: { user: user }, platform: "unknown", themeParams: {},
      openLink: function(u){ window.open(u, "_blank"); }, openTelegramLink: function(u){ location.href = u; },
      close: noop, ready: noop, expand: noop }, {
    get: function(t, k){ return k in t ? t[k] : stub(); }
  });
  window.Telegram = { WebApp: app };
})();
</script>"""


async def index_page(request):
    """Отдаёт мини-апп. Подставляет username бота и относительный адрес API,
    поэтому в index.html вручную ничего вписывать не нужно."""
    path = os.path.join(config.WEBAPP_DIR, "index.html")
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return web.Response(status=404, text="index.html не найден (проверьте WEBAPP_DIR)")
    html = html.replace('botUsername: "StarlifyShopBot"', f'botUsername: "{D.get("bot_username") or "StarlifyShopBot"}"')
    html = html.replace('apiBase: ""', 'apiBase: "/api"', 1)
    script_tag = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
    html = html.replace(script_tag, script_tag + TG_SHIM, 1)
    html = html.replace('"Гость (откройте через Telegram)"', '"Гость (откройте через Telegram) ["+(window.__tgdiag||"")+"]"', 1)
    return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache"})


async def start(deps: dict):
    D.update(deps)
    app = web.Application(middlewares=[cors_mw], client_max_size=64 * 1024)
    app.add_routes([
        web.get("/", index_page),
        web.get("/index.html", index_page),
        web.get("/api/health", lambda r: web.json_response({"ok": True})),
        web.get("/api/profile", profile),
        web.post("/api/orders", create_order),
        web.get("/api/orders/{num}/check", check_order),
        web.post("/api/orders/{num}/proof", order_proof),
        web.post("/api/orders/{num}/cancel", cancel_order),
        web.post("/api/support/message", support_message),
        web.post("/api/topup", topup),
        web.post("/api/topup/{id}/paid", topup_paid),
        web.get("/api/topup/{id}/check", topup_check),
        web.post("/api/withdraw", withdraw),
        web.post("/api/ref_transfer", ref_transfer),
    ])
    assets = os.path.join(config.WEBAPP_DIR, "assets")
    if os.path.isdir(assets):
        app.router.add_static("/assets/", assets)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, config.WEBAPI_HOST, config.WEBAPI_PORT).start()
    logger.warning("Mini App API запущен на %s:%s", config.WEBAPI_HOST, config.WEBAPI_PORT)
    return asyncio.create_task(payment_watcher())
