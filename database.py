"""
Слой доступа к данным StarlifyShopBot.

Все функции открывают короткоживущее соединение через контекстный менеджер
`_connection()`, который гарантирует commit/rollback и закрытие соединения
даже при исключении (в исходной версии соединение могло "утечь", если
ошибка происходила между connect() и close()).

Строки результатов возвращаются как sqlite3.Row: их можно, как и раньше,
читать по индексу (row[0], row[10]...), а в новом коде — по имени столбца
(row["order_num"]), что надёжнее при изменении схемы.
"""

import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from timeutil import now_kyiv

from config import DB_PATH

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("НОВЫЙ", "ОЖИДАНИЕ_ОПЛАТЫ", "НА_ПРОВЕРКЕ", "НА_РАССМОТРЕНИИ")


@contextmanager
def _connection():
    """Контекстный менеджер соединения: commit при успехе, rollback при ошибке."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with _connection() as conn:
        cursor = conn.cursor()

        # Разрешает параллельное чтение во время записи — меньше "database is locked".
        cursor.execute("PRAGMA journal_mode = WAL")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                username TEXT,
                reg_date TEXT,
                orders_count INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0.0,
                referrer_id INTEGER DEFAULT NULL,
                ref_balance REAL DEFAULT 0.0,
                ref_earned REAL DEFAULT 0.0,
                ref_count INTEGER DEFAULT 0,
                language TEXT DEFAULT 'ru'
            )
        ''')

        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        migrations = {
            "referrer_id": "INTEGER DEFAULT NULL",
            "ref_balance": "REAL DEFAULT 0.0",
            "ref_earned": "REAL DEFAULT 0.0",   # только бонусы с рефералов (без пополнений)
            "ref_count": "INTEGER DEFAULT 0",
            "ref_bonus": "REAL DEFAULT 0.0",   # реферальный баланс: бонусы, ещё не переведённые на основной баланс
            "language": "TEXT DEFAULT 'ru'"
        }
        for col, col_type in migrations.items():
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_type TEXT,
                details TEXT,
                amount REAL,
                status TEXT,
                proof_file_id TEXT,
                proof_type TEXT,
                username_target TEXT,
                date TEXT,
                order_num TEXT UNIQUE
            )
        ''')

        # Миграция: колонка для привязки конкретного CryptoBot-инвойса к заказу.
        # Без этой привязки пользователь мог подставить invoice_id от своего же
        # оплаченного дешёвого счёта в callback_data чужого/дорогого заказа
        # и получить его бесплатно закрытым как оплаченный.
        cursor.execute("PRAGMA table_info(orders)")
        existing_order_cols = {row[1] for row in cursor.fetchall()}
        if "crypto_invoice_id" not in existing_order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN crypto_invoice_id TEXT")
        # Заказ оплачен с баланса магазина (при отклонении деньги возвращаются на баланс).
        if "paid_from_balance" not in existing_order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN paid_from_balance INTEGER DEFAULT 0")

        # Миграция: добавляем UNIQUE индекс если его нет
        cursor.execute("PRAGMA index_list(orders)")
        idx_names = {row[1] for row in cursor.fetchall()}
        if "idx_order_num_unique" not in idx_names:
            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_order_num_unique ON orders(order_num)")
            except Exception:
                logger.warning("Не удалось создать уникальный индекс order_num", exc_info=True)

        # Индексы под частые запросы (антиспам-проверка, активные заказы, статус).
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id)")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                method TEXT,
                amount REAL,
                currency TEXT,
                status TEXT,
                external_id TEXT,
                date TEXT
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_donations_external_id ON donations(external_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_donations_status ON donations(status)")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL,
                status TEXT NOT NULL,
                invoice_id TEXT,
                date TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                requisites TEXT,
                status TEXT NOT NULL,
                date TEXT
            )
        ''')

        default_settings = {
            "hidden_sections": os.getenv("HIDE_SECTIONS", "").strip().lower(),
            "stars_rate": "0.77",
            "premium_3m": "450.00",
            "premium_6m": "800.00",
            "premium_1y": "1500.00",
            "card_number": "4441 1111 2222 3333",
            "card_name": "STARLIFY SHOP",
            "support_contact": "@StarlifyAdmin",
            "reviews_link": "https://t.me/starlify_reviews",
            "referral_bonus_percent": "5",
            # --- Курсы и лимиты (меняются в /admin -> Изменение цен/инфо) ---
            "usd_rate": "41.67",   # 1 доллар = N грн (по нему считаются крипто-счета)
            "ton_rate": "0",       # 1 TON = N грн; 0 = брать живой курс из CryptoBot
            "stars_min": "50",     # минимальное количество звёзд в заказе
            # --- Скидка в честь открытия (на покупку звёзд) ---
            "stars_discount_enabled": "1",
            "stars_discount_percent": "20",
            # {percent} автоматически подставляется текущим значением скидки
            "stars_discount_text": "🔥🎉 СКИДКА -{percent}% В ЧЕСТЬ ОТКРЫТИЯ! Успей купить дешевле! 🎉🔥"
        }

        for key, val in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))


def get_setting(key):
    with _connection() as conn:
        res = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return res[0] if res else None


def set_setting(key, value):
    with _connection() as conn:
        conn.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))


def add_user(tg_id, username, referrer_id=None):
    with _connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tg_id FROM users WHERE tg_id = ?", (tg_id,))
        is_new = not cursor.fetchone()
        if is_new:
            date_str = now_kyiv().strftime("%d.%m.%Y %H:%M")
            if referrer_id == tg_id:
                referrer_id = None
            cursor.execute(
                "INSERT INTO users (tg_id, username, reg_date, referrer_id) VALUES (?, ?, ?, ?)",
                (tg_id, username, date_str, referrer_id)
            )
            if referrer_id:
                cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE tg_id = ?", (referrer_id,))
        return is_new


def get_referrer(tg_id):
    with _connection() as conn:
        res = conn.execute("SELECT referrer_id FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return res[0] if res else None


def add_ref_bonus(referrer_id, amount):
    with _connection() as conn:
        conn.execute("UPDATE users SET ref_bonus = ref_bonus + ?, ref_earned = ref_earned + ? WHERE tg_id = ?",
                     (amount, amount, referrer_id))


def get_ref_stats(tg_id):
    with _connection() as conn:
        res = conn.execute("SELECT ref_count, ref_balance FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return tuple(res) if res else (0, 0.0)


def get_ref_bonus(tg_id) -> float:
    """Реферальный баланс: бонусы за друзей, которые ещё не переведены на основной баланс."""
    with _connection() as conn:
        res = conn.execute("SELECT ref_bonus FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return round(float(res[0] or 0.0), 2) if res else 0.0


def transfer_ref_bonus(tg_id) -> float:
    """Атомарно переводит весь реферальный баланс на основной. Возвращает сумму (0 — переводить нечего)."""
    with _connection() as conn:
        row = conn.execute("SELECT ref_bonus FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        amount = round(float(row[0] or 0.0), 2) if row else 0.0
        if amount <= 0:
            return 0.0
        cur = conn.execute(
            "UPDATE users SET ref_balance = ref_balance + ?, ref_bonus = MAX(ref_bonus - ?, 0) "
            "WHERE tg_id = ? AND ref_bonus >= ?",
            (amount, amount, tg_id, amount))
        return amount if cur.rowcount == 1 else 0.0


def get_ref_earned(tg_id) -> float:
    """Сколько пользователь заработал именно на рефералах (пополнения сюда не входят)."""
    with _connection() as conn:
        res = conn.execute("SELECT ref_earned FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return float(res[0] or 0.0) if res else 0.0


def spend_ref_balance(tg_id, amount):
    with _connection() as conn:
        cursor = conn.cursor()
        res = cursor.execute("SELECT ref_balance FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if not res or res[0] < amount:
            return False
        cursor.execute("UPDATE users SET ref_balance = ref_balance - ? WHERE tg_id = ?", (amount, tg_id))
        return True


def get_language(tg_id):
    with _connection() as conn:
        res = conn.execute("SELECT language FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        return res[0] if res and res[0] else "ru"


def set_language(tg_id, lang_code):
    with _connection() as conn:
        conn.execute("UPDATE users SET language = ? WHERE tg_id = ?", (lang_code, tg_id))


def get_user(tg_id):
    with _connection() as conn:
        return conn.execute(
            "SELECT tg_id, username, reg_date, orders_count, total_spent FROM users WHERE tg_id = ?",
            (tg_id,)
        ).fetchone()


def get_all_users():
    with _connection() as conn:
        res = conn.execute("SELECT tg_id FROM users").fetchall()
        return [r[0] for r in res]


def _generate_order_num():
    """Генерирует гарантированно уникальный номер заказа через UUID4."""
    short = uuid.uuid4().hex[:8].upper()
    date_part = now_kyiv().strftime('%Y%m%d')
    return f"ORD-{date_part}-{short}"


def has_open_order(user_id):
    """Возвращает True, если у пользователя есть незакрытый заказ (антиспам)."""
    return get_open_order(user_id) is not None


def get_open_order(user_id):
    """Возвращает незакрытый заказ пользователя (id, order_num, status) или None."""
    placeholders = ",".join("?" * len(OPEN_STATUSES))
    with _connection() as conn:
        res = conn.execute(
            f"SELECT id, order_num, status FROM orders WHERE user_id = ? AND status IN ({placeholders}) LIMIT 1",
            (user_id, *OPEN_STATUSES)
        ).fetchone()
        return res


def create_order(user_id, item_type, details, amount, username_target):
    date_str = now_kyiv().strftime("%d.%m.%Y %H:%M")

    # Гарантируем уникальность: пробуем до 5 раз (коллизия UUID практически невозможна)
    for _ in range(5):
        order_num = _generate_order_num()
        try:
            with _connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO orders (user_id, item_type, details, amount, status, username_target, date, order_num)
                    VALUES (?, ?, ?, ?, 'НОВЫЙ', ?, ?, ?)
                ''', (user_id, item_type, details, amount, username_target, date_str, order_num))
                order_id = cursor.lastrowid
                return order_id, order_num
        except sqlite3.IntegrityError:
            continue

    raise RuntimeError("Не удалось сгенерировать уникальный номер заказа")


def set_order_crypto_invoice(order_id, invoice_id):
    """Привязывает CryptoBot-инвойс к заказу сразу при его создании."""
    with _connection() as conn:
        conn.execute(
            "UPDATE orders SET crypto_invoice_id = ? WHERE id = ?",
            (str(invoice_id), order_id)
        )


def update_order_status(order_id, status, proof_file_id=None, proof_type=None):
    with _connection() as conn:
        cursor = conn.cursor()

        # Запоминаем статус ДО обновления — нужно, чтобы понять, первый ли это
        # переход в "ВЫПОЛНЕН" (защита от повторного начисления бонусов).
        prev_row = cursor.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        prev_status = prev_row[0] if prev_row else None

        if proof_file_id and proof_type:
            cursor.execute(
                "UPDATE orders SET status = ?, proof_file_id = ?, proof_type = ? WHERE id = ?",
                (status, proof_file_id, proof_type, order_id)
            )
        else:
            cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))

        # БАГ №1 (фикс): начисляем orders_count/total_spent/реф.бонус только
        # при ПЕРВОМ переходе заказа в статус "ВЫПОЛНЕН". Если заказ уже был
        # выполнен и update_order_status вызвали повторно (двойной клик,
        # повторный /accept и т.п.) — бонусы повторно не начисляются.
        # Возврат денег: заказ, оплаченный с баланса, отклонён/отменён, пока был открыт.
        # Срабатывает ровно один раз (после первого перехода prev_status уже не «открытый»).
        if status == 'ОТКЛОНЕН' and prev_status in OPEN_STATUSES:
            paid = cursor.execute(
                "SELECT user_id, amount, paid_from_balance FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if paid and paid[2]:
                cursor.execute(
                    "UPDATE users SET ref_balance = ref_balance + ? WHERE tg_id = ?",
                    (round(float(paid[1]), 2), paid[0])
                )

        if status == 'ВЫПОЛНЕН' and prev_status != 'ВЫПОЛНЕН':
            order = cursor.execute("SELECT user_id, amount FROM orders WHERE id = ?", (order_id,)).fetchone()
            if order:
                uid, amt = order
                cursor.execute(
                    "UPDATE users SET orders_count = orders_count + 1, total_spent = total_spent + ? WHERE tg_id = ?",
                    (amt, uid)
                )

                # Реферальный бонус начисляется за КАЖДЫЙ выполненный заказ, а не только за первый.
                ref_row = cursor.execute("SELECT referrer_id FROM users WHERE tg_id = ?", (uid,)).fetchone()
                if ref_row and ref_row[0]:
                    referrer_id = ref_row[0]
                    pct_row = cursor.execute(
                        "SELECT value FROM settings WHERE key = 'referral_bonus_percent'"
                    ).fetchone()
                    bonus_percent = float(pct_row[0]) if pct_row else 5.0
                    bonus_amount = round(amt * bonus_percent / 100, 2)
                    cursor.execute(
                        "UPDATE users SET ref_bonus = ref_bonus + ?, ref_earned = ref_earned + ? WHERE tg_id = ?",
                        (bonus_amount, bonus_amount, referrer_id)
                    )


ORDER_COLUMNS = (
    "id, user_id, item_type, details, amount, status, proof_file_id, proof_type, "
    "username_target, date, order_num, crypto_invoice_id"
)
# Индексы полей в кортеже заказа (для читаемости в main.py):
# 0=id 1=user_id 2=item_type 3=details 4=amount 5=status 6=proof_file_id
# 7=proof_type 8=username_target 9=date 10=order_num 11=crypto_invoice_id


def pay_order_from_balance(user_id, order_id, amount) -> bool:
    """Атомарно: списывает сумму с баланса И переводит заказ в «НА_РАССМОТРЕНИИ».
    False — если на балансе не хватает денег (тогда ничего не меняется)."""
    amount = round(float(amount), 2)
    with _connection() as conn:
        # Сначала «занимаем» заказ: оплатить можно только неоплаченный заказ его владельца.
        # Это защищает от двойного списания при повторном нажатии кнопки.
        cur = conn.execute(
            "UPDATE orders SET status = 'НА_РАССМОТРЕНИИ', paid_from_balance = 1 "
            "WHERE id = ? AND user_id = ? AND status IN ('НОВЫЙ', 'ОЖИДАНИЕ_ОПЛАТЫ')",
            (order_id, user_id))
        if cur.rowcount != 1:
            return False
        cur = conn.execute(
            "UPDATE users SET ref_balance = ref_balance - ? WHERE tg_id = ? AND ref_balance >= ?",
            (amount, user_id, amount))
        if cur.rowcount != 1:
            conn.rollback()          # не хватило денег — заказ остаётся как был
            return False
        return True


def is_paid_from_balance(order_id) -> bool:
    with _connection() as conn:
        res = conn.execute("SELECT paid_from_balance FROM orders WHERE id = ?", (order_id,)).fetchone()
        return bool(res and res[0])


def get_order(order_id):
    with _connection() as conn:
        return conn.execute(
            f"SELECT {ORDER_COLUMNS} FROM orders WHERE id = ?",
            (order_id,)
        ).fetchone()


def get_pending_crypto_orders():
    """Заказы, ожидающие оплаты по счёту CryptoBot (для фонового авто-закрытия)."""
    with _connection() as conn:
        return conn.execute(
            f"SELECT {ORDER_COLUMNS} FROM orders "
            "WHERE status = 'ОЖИДАНИЕ_ОПЛАТЫ' AND crypto_invoice_id IS NOT NULL AND crypto_invoice_id != ''"
        ).fetchall()


def get_order_by_num(order_num):
    with _connection() as conn:
        return conn.execute(
            f"SELECT {ORDER_COLUMNS} FROM orders WHERE order_num = ?",
            (order_num,)
        ).fetchone()


def get_user_orders(user_id):
    with _connection() as conn:
        return conn.execute(
            "SELECT id, item_type, details, amount, status, date, order_num "
            "FROM orders WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        ).fetchall()


def get_orders_by_status(status):
    with _connection() as conn:
        return conn.execute(
            "SELECT id, user_id, item_type, amount, status, order_num FROM orders WHERE status = ? ORDER BY id DESC",
            (status,)
        ).fetchall()


def get_active_orders():
    """Возвращает все незакрытые заказы для админ-панели."""
    placeholders = ",".join("?" * len(OPEN_STATUSES))
    with _connection() as conn:
        return conn.execute(
            f"""SELECT o.id, o.user_id, u.username, o.item_type, o.details, o.amount, o.status,
                       o.username_target, o.date, o.order_num
                FROM orders o
                LEFT JOIN users u ON o.user_id = u.tg_id
                WHERE o.status IN ({placeholders})
                ORDER BY o.id DESC""",
            OPEN_STATUSES
        ).fetchall()


def delete_order_db(order_id):
    with _connection() as conn:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))


def add_donation(user_id, method, amount, currency, status, external_id=None):
    """Записывает донат. method: 'stars' | 'crypto'. status: 'PENDING' | 'PAID'."""
    with _connection() as conn:
        cursor = conn.execute(
            "INSERT INTO donations (user_id, method, amount, currency, status, external_id, date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, method, amount, currency, status, str(external_id) if external_id is not None else None,
             now_kyiv().strftime("%d.%m.%Y %H:%M")),
        )
        return cursor.lastrowid


def mark_donation_paid(external_id):
    with _connection() as conn:
        conn.execute(
            "UPDATE donations SET status = 'PAID' WHERE external_id = ? AND status != 'PAID'",
            (str(external_id),),
        )


def get_donation_by_external_id(external_id):
    with _connection() as conn:
        return conn.execute(
            "SELECT * FROM donations WHERE external_id = ?", (str(external_id),)
        ).fetchone()


def get_donations_stats():
    with _connection() as conn:
        cursor = conn.cursor()
        stars_total = cursor.execute(
            "SELECT SUM(amount) FROM donations WHERE method = 'stars' AND status = 'PAID'"
        ).fetchone()[0] or 0
        crypto_total = cursor.execute(
            "SELECT SUM(amount) FROM donations WHERE method = 'crypto' AND status = 'PAID'"
        ).fetchone()[0] or 0
        donors = cursor.execute(
            "SELECT COUNT(DISTINCT user_id) FROM donations WHERE status = 'PAID'"
        ).fetchone()[0]
        return stars_total, crypto_total, donors


def get_stats_db():
    with _connection() as conn:
        cursor = conn.cursor()
        total_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_orders = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        res_stars = cursor.execute(
            "SELECT SUM(CAST(details AS REAL)) FROM orders WHERE item_type = 'STARS' AND status = 'ВЫПОЛНЕН'"
        ).fetchone()[0]
        sold_stars = res_stars if res_stars else 0
        sold_premium = cursor.execute(
            "SELECT COUNT(*) FROM orders WHERE item_type = 'PREMIUM' AND status = 'ВЫПОЛНЕН'"
        ).fetchone()[0]
        res_rev = cursor.execute("SELECT SUM(amount) FROM orders WHERE status = 'ВЫПОЛНЕН'").fetchone()[0]
        revenue = res_rev if res_rev else 0
        # Реальные покупатели — те, у кого есть хотя бы один ВЫПОЛНЕННЫЙ заказ,
        # а не любой пользователь, когда-либо создававший заказ (включая отменённые).
        active_users = cursor.execute(
            "SELECT COUNT(DISTINCT user_id) FROM orders WHERE status = 'ВЫПОЛНЕН'"
        ).fetchone()[0]
        return total_users, total_orders, sold_stars, sold_premium, revenue, active_users


# ============== ПОПОЛНЕНИЯ / ВЫВОДЫ / БАЛАНС / НАСТРОЙКИ ИЗ ENV ==============
CARD_PLACEHOLDER = "4441 1111 2222 3333"


def apply_env_settings():
    """Настройки из переменных окружения (CARD_NUMBER, CARD_NAME, STARS_RATE, PREMIUM_3M/6M/1Y).
    Применяются при каждом старте — так они переживают очистку базы на бесплатном хостинге."""
    mapping = {
        "CARD_NUMBER": "card_number", "CARD_NAME": "card_name", "STARS_RATE": "stars_rate",
        "PREMIUM_3M": "premium_3m", "PREMIUM_6M": "premium_6m", "PREMIUM_1Y": "premium_1y",
        "SUPPORT_CONTACT": "support_contact",
    }
    for env_name, key in mapping.items():
        val = os.getenv(env_name, "").strip()
        if val:
            set_setting(key, val)


def card_is_configured() -> bool:
    num = (get_setting("card_number") or "").strip()
    return bool(num) and num != CARD_PLACEHOLDER


SECTION_KEYS = ("stars", "premium", "ton", "nft", "reviews", "channel", "support")


def get_hidden_sections() -> list[str]:
    raw = (get_setting("hidden_sections") or "")
    return [x for x in (p.strip() for p in raw.split(",")) if x in SECTION_KEYS]


def set_hidden_sections(keys) -> None:
    keys = [k for k in dict.fromkeys(keys) if k in SECTION_KEYS]
    with _connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('hidden_sections', ?)", (",".join(keys),))


def credit_balance(user_id, amount):
    with _connection() as conn:
        conn.execute("UPDATE users SET ref_balance = ref_balance + ? WHERE tg_id = ?", (round(float(amount), 2), user_id))


def debit_balance(user_id, amount) -> bool:
    """Атомарно списывает с баланса. False, если средств не хватает."""
    amount = round(float(amount), 2)
    with _connection() as conn:
        cur = conn.execute(
            "UPDATE users SET ref_balance = ref_balance - ? WHERE tg_id = ? AND ref_balance >= ?",
            (amount, user_id, amount))
        return cur.rowcount == 1


# ---- пополнения ----
TOPUP_OPEN = ("ОЖИДАНИЕ", "НА_ПРОВЕРКЕ")


def create_topup(user_id, amount, method, invoice_id=None):
    date_str = now_kyiv().strftime("%d.%m.%Y %H:%M")
    with _connection() as conn:
        cur = conn.execute(
            "INSERT INTO topups (user_id, amount, method, status, invoice_id, date) VALUES (?, ?, ?, 'ОЖИДАНИЕ', ?, ?)",
            (user_id, round(float(amount), 2), method, invoice_id, date_str))
        return cur.lastrowid


def get_topup(topup_id):
    with _connection() as conn:
        return conn.execute("SELECT * FROM topups WHERE id = ?", (topup_id,)).fetchone()


def set_topup_invoice(topup_id, invoice_id):
    with _connection() as conn:
        conn.execute("UPDATE topups SET invoice_id = ? WHERE id = ?", (str(invoice_id), topup_id))


def count_open_topups(user_id) -> int:
    with _connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM topups WHERE user_id = ? AND status IN ('ОЖИДАНИЕ','НА_ПРОВЕРКЕ')",
            (user_id,)).fetchone()[0]


def topup_transition(topup_id, from_statuses, to_status) -> bool:
    """Атомарный переход статуса. True только у одного из параллельных вызовов —
    защита от двойного зачисления."""
    ph = ",".join("?" * len(from_statuses))
    with _connection() as conn:
        cur = conn.execute(
            f"UPDATE topups SET status = ? WHERE id = ? AND status IN ({ph})",
            (to_status, topup_id, *from_statuses))
        return cur.rowcount == 1


def get_pending_crypto_topups():
    with _connection() as conn:
        return conn.execute(
            "SELECT * FROM topups WHERE method = 'crypto' AND status = 'ОЖИДАНИЕ' "
            "AND invoice_id IS NOT NULL AND invoice_id != ''").fetchall()


# ---- выводы ----
def create_withdrawal(user_id, amount, requisites):
    """Резервирует сумму (списывает с баланса) и создаёт заявку. None, если не хватает средств."""
    if not debit_balance(user_id, amount):
        return None
    date_str = now_kyiv().strftime("%d.%m.%Y %H:%M")
    with _connection() as conn:
        cur = conn.execute(
            "INSERT INTO withdrawals (user_id, amount, requisites, status, date) VALUES (?, ?, ?, 'ОЖИДАНИЕ', ?)",
            (user_id, round(float(amount), 2), requisites, date_str))
        return cur.lastrowid


def get_withdrawal(wd_id):
    with _connection() as conn:
        return conn.execute("SELECT * FROM withdrawals WHERE id = ?", (wd_id,)).fetchone()


def withdrawal_transition(wd_id, from_status, to_status) -> bool:
    with _connection() as conn:
        cur = conn.execute("UPDATE withdrawals SET status = ? WHERE id = ? AND status = ?", (to_status, wd_id, from_status))
        return cur.rowcount == 1
