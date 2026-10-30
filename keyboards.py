from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
import locales as loc


def main_menu(lang="ru"):
    rows = [
        [
            KeyboardButton(text=loc.t("menu.buy_stars", lang)),
            KeyboardButton(text=loc.t("menu.buy_premium", lang)),
        ],
        [
            KeyboardButton(text=loc.t("menu.profile", lang)),
            KeyboardButton(text=loc.t("menu.orders", lang)),
        ],
        [
            KeyboardButton(text=loc.t("menu.referral", lang)),
            KeyboardButton(text=loc.t("menu.settings", lang)),
        ],
        [
            KeyboardButton(text=loc.t("menu.support", lang)),
            KeyboardButton(text=loc.t("menu.reviews", lang)),
        ],
        [KeyboardButton(text=loc.t("menu.donate", lang))],
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        persistent=True,
    )


def cancel_kb(lang="ru"):
    labels = {"ru": "❌ Отмена", "en": "❌ Cancel", "ua": "❌ Скасувати"}
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=labels.get(lang, labels["ru"]))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def username_entry_kb(lang="ru", user_username: str = None):
    cancel_labels = {"ru": "❌ Отмена", "en": "❌ Cancel", "ua": "❌ Скасувати"}
    rows = [[KeyboardButton(text=cancel_labels.get(lang, cancel_labels["ru"]))]]
    if user_username:
        my_labels = {
            "ru": "👤 Свой юзернейм",
            "en": "👤 My username",
            "ua": "👤 Свій юзернейм",
        }
        rows.insert(0, [KeyboardButton(text=my_labels.get(lang, my_labels["ru"]))])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


MY_USERNAME_TEXTS = {"👤 Свой юзернейм", "👤 My username", "👤 Свій юзернейм"}
CANCEL_TEXTS = {"❌ Отмена", "❌ Cancel", "❌ Скасувати"}


def stars_preset_kb(lang="ru"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 50", callback_data="stars_preset_50"),
            InlineKeyboardButton(text="⭐ 100", callback_data="stars_preset_100"),
        ],
        [
            InlineKeyboardButton(text="⭐ 250", callback_data="stars_preset_250"),
            InlineKeyboardButton(text="⭐ 500", callback_data="stars_preset_500"),
        ],
        [
            InlineKeyboardButton(text="⭐ 1000", callback_data="stars_preset_1000"),
            InlineKeyboardButton(text="✏️ Своё количество", callback_data="stars_preset_custom"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="stars_cancel")],
    ])


def settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Язык / Language", callback_data="settings_language")]
    ])


def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_ua")],
    ])


def referral_kb(ref_balance, ref_bonus=0.0):
    buttons = [[InlineKeyboardButton(text="🔄 Обновить", callback_data="ref_refresh")]]
    if ref_bonus and ref_bonus > 0:
        buttons.append([InlineKeyboardButton(
            text=f"💸 Вывести на баланс ({ref_bonus:.2f} грн)",
            callback_data="ref_transfer",
        )])
    if ref_balance and ref_balance > 0:
        buttons.append([
            InlineKeyboardButton(
                text="💸 Использовать баланс при оплате",
                callback_data="ref_info_usage",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pay_method_kb(order_id, crypto_url=None, balance=0.0, amount=0.0):
    buttons = [[
        InlineKeyboardButton(
            text="💳 Перевод на карту",
            callback_data=f"pay_card_{order_id}",
        )
    ]]
    if crypto_url:
        buttons.append([InlineKeyboardButton(
            text="🪙 Через CryptoBot API",
            url=crypto_url,
        )])
    else:
        buttons.append([InlineKeyboardButton(
            text="🪙 Через CryptoBot",
            callback_data=f"pay_crypto_{order_id}",
        )])
    if balance and balance > 0:
        label = f"💰 Оплатить с баланса ({balance:.2f} грн)"
        buttons.insert(0, [InlineKeyboardButton(text=label, callback_data=f"balpay_{order_id}")])
    buttons.append([InlineKeyboardButton(
        text="❌ Отменить заказ",
        callback_data=f"cancel_order_{order_id}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def premium_choice_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Premium на 3 мес.", callback_data="prem_3m")],
        [InlineKeyboardButton(text="Premium на 6 мес.", callback_data="prem_6m")],
        [InlineKeyboardButton(text="Premium на 1 год", callback_data="prem_1y")],
        [InlineKeyboardButton(
            text="🔑 Premium со входом (через поддержку)",
            callback_data="prem_login_support",
        )],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="premium_cancel")],
    ])


def i_paid_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💸 Я оплатил(а)",
            callback_data=f"confirm_paid_{order_id}",
        )],
        [InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data=f"cancel_order_{order_id}",
        )],
    ])


def proof_type_selection_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Скриншот (Фото)", callback_data="proof_photo")],
        [InlineKeyboardButton(text="📄 Квитанция (PDF)", callback_data="proof_pdf")],
        [InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data=f"cancel_order_{order_id}",
        )],
    ])


def admin_decision_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ На рассмотрение", callback_data=f"adm_review_{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{order_id}")],
    ])


def admin_balance_order_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнен", callback_data=f"adm_done_{order_id}")],
        [InlineKeyboardButton(
            text="❌ Отклонить (вернуть на баланс)",
            callback_data=f"adm_reject_{order_id}",
        )],
    ])


def admin_crypto_order_kb(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выполнен", callback_data=f"adm_done_{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_reject_{order_id}")],
    ])


def topup_decision_kb(topup_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Зачислить на баланс",
            callback_data=f"topup_ok_{topup_id}",
        )],
        [InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"topup_no_{topup_id}",
        )],
    ])


def withdraw_decision_kb(wd_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выплачено", callback_data=f"wd_ok_{wd_id}")],
        [InlineKeyboardButton(
            text="❌ Отклонить (вернуть на баланс)",
            callback_data=f"wd_no_{wd_id}",
        )],
    ])


def close_support_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Вопрос решен (Закрыть)",
            callback_data="close_ticket",
        )]
    ])


def admin_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Скидка на открытие", callback_data="admin_discount_hub")],
        [InlineKeyboardButton(text="⚙️ Изменение цен/инфо", callback_data="admin_settings")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📋 Активные заказы", callback_data="admin_active_orders")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    ])


def admin_discount_kb(enabled: bool, percent: float):
    toggle_text = (
        "✅ Скидка ВКЛЮЧЕНА — выключить"
        if enabled
        else "🚫 Скидка ВЫКЛЮЧЕНА — включить"
    )
    percent_str = f"{percent:g}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="discount_toggle")],
        [InlineKeyboardButton(
            text=f"✏️ Изменить процент (сейчас {percent_str}%)",
            callback_data="set_stars_discount_percent",
        )],
        [InlineKeyboardButton(
            text="📝 Изменить текст скидки",
            callback_data="set_stars_discount_text",
        )],
        [InlineKeyboardButton(
            text="◀️ Назад в админ-панель",
            callback_data="admin_back_to_menu",
        )],
    ])


def donate_method_kb(lang="ru"):
    labels = {
        "ru": ("⭐ Telegram Stars", "🪙 TON / USDT", "❌ Отмена"),
        "en": ("⭐ Telegram Stars", "🪙 TON / USDT", "❌ Cancel"),
        "ua": ("⭐ Telegram Stars", "🪙 TON / USDT", "❌ Скасувати"),
    }
    stars_label, crypto_label, cancel_label = labels.get(lang, labels["ru"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=stars_label, callback_data="donate_method_stars")],
        [InlineKeyboardButton(text=crypto_label, callback_data="donate_method_crypto")],
        [InlineKeyboardButton(text=cancel_label, callback_data="donate_cancel")],
    ])


def donate_stars_kb(lang="ru"):
    cancel_label = {
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "ua": "❌ Скасувати",
    }.get(lang, "❌ Отмена")
    custom_label = {
        "ru": "✏️ Своё количество",
        "en": "✏️ Custom amount",
        "ua": "✏️ Своя кількість",
    }.get(lang, "✏️ Своё количество")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ 25", callback_data="donate_stars_25"),
            InlineKeyboardButton(text="⭐ 50", callback_data="donate_stars_50"),
        ],
        [
            InlineKeyboardButton(text="⭐ 100", callback_data="donate_stars_100"),
            InlineKeyboardButton(text="⭐ 250", callback_data="donate_stars_250"),
        ],
        [
            InlineKeyboardButton(text="⭐ 500", callback_data="donate_stars_500"),
            InlineKeyboardButton(text=custom_label, callback_data="donate_stars_custom"),
        ],
        [InlineKeyboardButton(text=cancel_label, callback_data="donate_cancel")],
    ])


def donate_crypto_kb(lang="ru"):
    cancel_label = {
        "ru": "❌ Отмена",
        "en": "❌ Cancel",
        "ua": "❌ Скасувати",
    }.get(lang, "❌ Отмена")
    custom_label = {
        "ru": "✏️ Своя сумма",
        "en": "✏️ Custom amount",
        "ua": "✏️ Своя сума",
    }.get(lang, "✏️ Своя сумма")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 $", callback_data="donate_crypto_1"),
            InlineKeyboardButton(text="3 $", callback_data="donate_crypto_3"),
            InlineKeyboardButton(text="5 $", callback_data="donate_crypto_5"),
        ],
        [
            InlineKeyboardButton(text="10 $", callback_data="donate_crypto_10"),
            InlineKeyboardButton(text="25 $", callback_data="donate_crypto_25"),
        ],
        [InlineKeyboardButton(text=custom_label, callback_data="donate_crypto_custom")],
        [InlineKeyboardButton(text=cancel_label, callback_data="donate_cancel")],
    ])


def donate_crypto_pay_kb(pay_url, invoice_id, lang="ru"):
    labels = {
        "ru": ("💳 Оплатить", "✅ Я оплатил", "❌ Отмена"),
        "en": ("💳 Pay", "✅ I've paid", "❌ Cancel"),
        "ua": ("💳 Оплатити", "✅ Я оплатив", "❌ Скасувати"),
    }
    pay_label, paid_label, cancel_label = labels.get(lang, labels["ru"])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=pay_label, url=pay_url)],
        [InlineKeyboardButton(
            text=paid_label,
            callback_data=f"donate_check_{invoice_id}",
        )],
        [InlineKeyboardButton(text=cancel_label, callback_data="donate_cancel")],
    ])


def admin_settings_list():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Скидка на открытие", callback_data="admin_discount_hub")],
        [InlineKeyboardButton(text="Курс Stars (грн за 1 ⭐)", callback_data="set_stars_rate")],
        [InlineKeyboardButton(text="Мин. количество Stars", callback_data="set_stars_min")],
        [InlineKeyboardButton(text="Курс TON (грн)", callback_data="set_ton_rate")],
        [InlineKeyboardButton(text="Курс доллара (грн)", callback_data="set_usd_rate")],
        [InlineKeyboardButton(text="Premium 3 мес.", callback_data="set_premium_3m")],
        [InlineKeyboardButton(text="Premium 6 мес.", callback_data="set_premium_6m")],
        [InlineKeyboardButton(text="Premium 1 год", callback_data="set_premium_1y")],
        [InlineKeyboardButton(text="Номер карты", callback_data="set_card_number")],
        [InlineKeyboardButton(text="Владелец карты", callback_data="set_card_name")],
        [InlineKeyboardButton(text="Контакты поддержки", callback_data="set_support_contact")],
        [InlineKeyboardButton(text="Ссылка на отзывы", callback_data="set_reviews_link")],
        [InlineKeyboardButton(text="% реферальной программы", callback_data="set_referral_bonus_percent")],
    ])
    
