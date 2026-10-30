"""
Словарь локализации для StarlifyShopBot.
Использование: t("menu.profile", lang) -> переведенная строка.
"""

STRINGS = {
    "menu.buy_stars": {"ru": "⭐️ Купить звезды", "en": "⭐️ Buy Stars", "ua": "⭐️ Купити зірки"},
    "menu.buy_premium": {"ru": "💎 Купить Premium", "en": "💎 Buy Premium", "ua": "💎 Купити Premium"},
    "menu.profile": {"ru": "👤 Профиль", "en": "👤 Profile", "ua": "👤 Профіль"},
    "menu.orders": {"ru": "📦 Мои заказы", "en": "📦 My Orders", "ua": "📦 Мої замовлення"},
    "menu.referral": {"ru": "🤝 Реферальная программа", "en": "🤝 Referral Program", "ua": "🤝 Реферальна програма"},
    "menu.settings": {"ru": "⚙️ Настройки", "en": "⚙️ Settings", "ua": "⚙️ Налаштування"},
    "menu.support": {"ru": "🆘 Поддержка", "en": "🆘 Support", "ua": "🆘 Підтримка"},
    "menu.reviews": {"ru": "⭐️ Отзывы", "en": "⭐️ Reviews", "ua": "⭐️ Відгуки"},
    "menu.shop": {"ru": "🛍 Открыть магазин", "en": "🛍 Open shop", "ua": "🛍 Відкрити магазин"},
    "menu.donate": {"ru": "💖 Поддержать проект", "en": "💖 Support the project", "ua": "💖 Підтримати проєкт"},

    "start.welcome": {
        "ru": (
            "🌟 Добро пожаловать в StarlifyShop!\n"
            "⭐ StarlifyShop — удобный сервис для покупки Telegram Stars по выгодным ценам.\n\n"
            "💎 Что вы получаете?\n"
            "• ⚡ Быструю обработку заказов.\n"
            "• 💰 Честные и выгодные цены.\n"
            "• 🔒 Безопасную оплату.\n"
            "• ✅ Гарантию выполнения каждого оплаченного заказа.\n"
            "• 🛟 Оперативную поддержку, если возникнут вопросы.\n\n"
            "🛒 Как купить?\n"
            "Выберите количество ⭐ Stars.\n"
            "Оплатите заказ удобным способом.\n"
            "Получите Stars в кратчайшие сроки.\n\n"
            "🛡️ Наша гарантия\n"
            "Мы ценим доверие каждого клиента. Если при выполнении заказа возникнет проблема по нашей вине, мы обязательно решим ситуацию: повторно выполним заказ или вернем средства в соответствии с условиями сервиса.\n\n"
            "📩 Если у вас появились вопросы — обращайтесь в поддержку, мы всегда готовы помочь.\n"
            "✨ Спасибо, что выбрали StarlifyShop! Желаем приятных покупок! ⭐"
        ),
        "en": (
            "🌟 Welcome to StarlifyShop!\n"
            "⭐ StarlifyShop is a convenient service for buying Telegram Stars at great prices.\n\n"
            "💎 What you get:\n"
            "• ⚡ Fast order processing.\n"
            "• 💰 Fair and competitive prices.\n"
            "• 🔒 Secure payment.\n"
            "• ✅ A guarantee for every paid order.\n"
            "• 🛟 Responsive support whenever you need it.\n\n"
            "🛒 How to buy?\n"
            "Choose how many ⭐ Stars you want.\n"
            "Pay using a convenient method.\n"
            "Receive your Stars in no time.\n\n"
            "🛡️ Our guarantee\n"
            "We value every customer's trust. If something goes wrong on our end, we'll fix it — either by redoing the order or refunding you per our terms.\n\n"
            "📩 Got questions? Reach out to support, we're always glad to help.\n"
            "✨ Thanks for choosing StarlifyShop! Enjoy your purchase! ⭐"
        ),
        "ua": (
            "🌟 Вітаємо в StarlifyShop!\n"
            "⭐ StarlifyShop — зручний сервіс для купівлі Telegram Stars за вигідними цінами.\n\n"
            "💎 Що ви отримуєте?\n"
            "• ⚡ Швидку обробку замовлень.\n"
            "• 💰 Чесні та вигідні ціни.\n"
            "• 🔒 Безпечну оплату.\n"
            "• ✅ Гарантію виконання кожного оплаченого замовлення.\n"
            "• 🛟 Оперативну підтримку за потреби.\n\n"
            "🛒 Як купити?\n"
            "Оберіть кількість ⭐ Stars.\n"
            "Оплатіть замовлення зручним способом.\n"
            "Отримайте Stars якнайшвидше.\n\n"
            "🛡️ Наша гарантія\n"
            "Ми цінуємо довіру кожного клієнта. Якщо виникне проблема з нашої вини, ми обов'язково вирішимо ситуацію: повторно виконаємо замовлення або повернемо кошти.\n\n"
            "📩 Маєте питання — звертайтеся до підтримки, ми завжди готові допомогти.\n"
            "✨ Дякуємо, що обрали StarlifyShop! Приємних покупок! ⭐"
        ),
    },

    "profile.title": {"ru": "Личный кабинет клиента", "en": "Customer Profile", "ua": "Особистий кабінет клієнта"},
    "profile.id": {"ru": "Ваш ID", "en": "Your ID", "ua": "Ваш ID"},
    "profile.username": {"ru": "Юзернейм", "en": "Username", "ua": "Юзернейм"},
    "profile.not_set": {"ru": "не указан", "en": "not set", "ua": "не вказано"},
    "profile.reg_date": {"ru": "Регистрация", "en": "Registered", "ua": "Реєстрація"},
    "profile.orders_count": {"ru": "Успешных заказов", "en": "Successful orders", "ua": "Успішних замовлень"},
    "profile.total_spent": {"ru": "Сумма покупок", "en": "Total spent", "ua": "Сума покупок"},
    "profile.ref_count": {"ru": "Рефералов", "en": "Referrals", "ua": "Рефералів"},
    "profile.ref_balance": {"ru": "Баланс", "en": "Balance", "ua": "Баланс"},

    "referral.title": {"ru": "🤝 Реферальная программа", "en": "🤝 Referral Program", "ua": "🤝 Реферальна програма"},
    "referral.desc": {
        "ru": "Приглашайте друзей и получайте {pct}% от суммы каждого их оплаченного заказа на свой баланс!",
        "en": "Invite friends and earn {pct}% of every paid order they make, credited to your balance!",
        "ua": "Запрошуйте друзів і отримуйте {pct}% від суми кожного їхнього оплаченого замовлення на свій баланс!"
    },
    "referral.link": {"ru": "🔗 Ваша ссылка", "en": "🔗 Your link", "ua": "🔗 Ваше посилання"},
    "referral.invited": {"ru": "👥 Приглашено", "en": "👥 Invited", "ua": "👥 Запрошено"},
    "referral.earned": {"ru": "🎁 Заработано с рефералов", "en": "🎁 Earned from referrals", "ua": "🎁 Зароблено з рефералів"},
    "referral.balance": {"ru": "💰 Баланс", "en": "💰 Balance", "ua": "💰 Баланс"},
    "referral.bonus": {"ru": "🎁 Реферальный баланс", "en": "🎁 Referral balance", "ua": "🎁 Реферальний баланс"},
    "referral.usage_hint": {
        "ru": "Баланс можно потратить на следующую покупку: при выборе способа оплаты нажмите «💰 Оплатить с баланса» — сумма спишется автоматически.",
        "en": "You can spend your balance on your next purchase: when choosing a payment method, tap “💰 Pay from balance” — the amount is deducted automatically.",
        "ua": "Баланс можна витратити на наступну покупку: обираючи спосіб оплати, натисніть «💰 Оплатити з балансу» — сума спишеться автоматично."
    },

    "settings.title": {"ru": "⚙️ Настройки", "en": "⚙️ Settings", "ua": "⚙️ Налаштування"},
    "settings.current_lang": {"ru": "Текущий язык интерфейса", "en": "Current interface language", "ua": "Поточна мова інтерфейсу"},
    "settings.choose_lang": {"ru": "🌐 Выберите язык:", "en": "🌐 Choose your language:", "ua": "🌐 Оберіть мову:"},

    # --- Покупка звезд ---
    "stars.start": {
        "ru": "Покупка Telegram Stars\n\nТекущий курс за 1 звезду: {prices}\n\nВведите количество звезд для покупки:",
        "en": "Buy Telegram Stars\n\nCurrent rate per 1 star: {prices}\n\nEnter the number of stars you want to buy:",
        "ua": "Купівля Telegram Stars\n\nПоточний курс за 1 зірку: {prices}\n\nВведіть кількість зірок для купівлі:",
    },
    "stars.bad_count": {
        "ru": "Введите корректное число звезд (целое положительное число).",
        "en": "Please enter a valid number of stars (positive integer).",
        "ua": "Введіть коректну кількість зірок (ціле позитивне число).",
    },
    "stars.enter_username": {
        "ru": "Введите @username получателя звезд (аккаунта или канала):",
        "en": "Enter the @username of the recipient (account or channel):",
        "ua": "Введіть @username отримувача зірок (акаунту або каналу):",
    },
    "stars.bad_username": {
        "ru": "Ошибка! Юзернейм указан неверно. Используйте только латиницу (A–Z), цифры и знаки подчеркивания (минимум 5 символов). Введите корректный никнейм:",
        "en": "Invalid username! Use only Latin letters (A–Z), digits, and underscores (min 5 characters). Please re-enter:",
        "ua": "Помилка! Юзернейм вказано невірно. Використовуйте лише латиницю (A–Z), цифри та знаки підкреслення (мінімум 5 символів). Введіть коректний нікнейм:",
    },

    # --- Покупка Premium ---
    "prem.choose_period": {
        "ru": "Выберите период подписки Telegram Premium:",
        "en": "Choose your Telegram Premium subscription period:",
        "ua": "Оберіть термін підписки Telegram Premium:",
    },
    "prem.login_info": {
        "ru": (
            "🔑 Вы выбрали оформление Telegram Premium «со входом».\n\n"
            "Этот способ оформляется вручную через оператора поддержки, так как требует "
            "временного доступа к вашему аккаунту (логин/код подтверждения передаются "
            "напрямую оператору, бот их не запрашивает и не хранит).\n\n"
            "Опишите ниже, на какой срок хотите Premium — оператор свяжется с вами и "
            "проведёт оформление лично."
        ),
        "en": (
            "🔑 You chose Telegram Premium «with login».\n\n"
            "This is processed manually by a support operator, as it requires temporary access "
            "to your account (login/code is passed directly to the operator; the bot never "
            "requests or stores it).\n\n"
            "Describe below how long you want Premium — the operator will contact you personally."
        ),
        "ua": (
            "🔑 Ви обрали оформлення Telegram Premium «зі входом».\n\n"
            "Цей спосіб оформлюється вручну через оператора підтримки, оскільки потребує "
            "тимчасового доступу до вашого акаунту (логін/код передається безпосередньо оператору, "
            "бот їх не запитує і не зберігає).\n\n"
            "Опишіть нижче, на який термін бажаєте Premium — оператор зв'яжеться з вами особисто."
        ),
    },
    "prem.enter_username": {
        "ru": "Введите @username аккаунта, которому дарится подписка:",
        "en": "Enter the @username of the account to receive the subscription:",
        "ua": "Введіть @username акаунту, якому дарується підписка:",
    },

    # --- Оплата ---
    "pay.choose_method": {
        "ru": "\n\nВыберите метод оплаты:",
        "en": "\n\nChoose a payment method:",
        "ua": "\n\nОберіть метод оплати:",
    },
    "pay.card_text": {
        "ru": (
            "Оплата переводом на карту:\n\n"
            "Переведите сумму по реквизитам:\n"
            "Сумма: {price_str}\n"
            "Номер карты: {card_num}\n"
            "Получатель: {card_name}\n\n"
            "После выполнения перевода нажмите кнопку «Я оплатил(а)» ниже."
        ),
        "en": (
            "Payment by card transfer:\n\n"
            "Send the amount to:\n"
            "Amount: {price_str}\n"
            "Card number: {card_num}\n"
            "Recipient: {card_name}\n\n"
            "After completing the transfer, tap «I've paid» below."
        ),
        "ua": (
            "Оплата переказом на картку:\n\n"
            "Переведіть суму за реквізитами:\n"
            "Сума: {price_str}\n"
            "Номер картки: {card_num}\n"
            "Отримувач: {card_name}\n\n"
            "Після здійснення переказу натисніть кнопку «Я оплатив(ла)» нижче."
        ),
    },
    "pay.crypto_wait": {
        "ru": "🔄 Генерируем счет CryptoBot, подождите...",
        "en": "🔄 Generating CryptoBot invoice, please wait...",
        "ua": "🔄 Генеруємо рахунок CryptoBot, зачекайте...",
    },
    "pay.crypto_text": {
        "ru": (
            "Оплата через CryptoBot:\n\n"
            "Сумма счета: ${usd} ({price_str})\n\n"
            "Перейдите по ссылке ниже — в CryptoBot можно выбрать оплату в USDT или TON. "
            "После подтверждения транзакции нажмите кнопку «Проверить оплату»."
        ),
        "en": (
            "Payment via CryptoBot:\n\n"
            "Invoice amount: ${usd} ({price_str})\n\n"
            "Follow the link below — you can pay in USDT or TON inside CryptoBot. "
            "After the transaction is confirmed, tap «Verify payment»."
        ),
        "ua": (
            "Оплата через CryptoBot:\n\n"
            "Сума рахунку: ${usd} ({price_str})\n\n"
            "Перейдіть за посиланням нижче — у CryptoBot можна обрати оплату в USDT або TON. "
            "Після підтвердження транзакції натисніть кнопку «Перевірити оплату»."
        ),
    },
    "pay.crypto_btn_pay": {"ru": "🔗 Оплатить счет", "en": "🔗 Pay Invoice", "ua": "🔗 Оплатити рахунок"},
    "pay.crypto_btn_check": {"ru": "🔄 Проверить оплату", "en": "🔄 Verify Payment", "ua": "🔄 Перевірити оплату"},
    "pay.crypto_btn_cancel": {"ru": "❌ Отменить заказ", "en": "❌ Cancel Order", "ua": "❌ Скасувати замовлення"},
    "pay.crypto_fail": {
        "ru": "⚠️ Не удалось выставить счет через CryptoBot.\n\nПричина сбоя: {error}\n\nПожалуйста, исправьте проблему или обратитесь к администратору.",
        "en": "⚠️ Failed to create a CryptoBot invoice.\n\nReason: {error}\n\nPlease fix the issue or contact the administrator.",
        "ua": "⚠️ Не вдалося виставити рахунок через CryptoBot.\n\nПричина збою: {error}\n\nБудь ласка, виправте проблему або зверніться до адміністратора.",
    },
    "pay.verified": {
        "ru": "✅ Оплата успешно подтверждена! Ваш заказ принят в обработку.",
        "en": "✅ Payment confirmed! Your order has been accepted for processing.",
        "ua": "✅ Оплату успішно підтверджено! Ваше замовлення прийнято в обробку.",
    },
    "pay.not_confirmed": {
        "ru": "❌ Оплата не подтверждена.\n{detail}",
        "en": "❌ Payment not confirmed.\n{detail}",
        "ua": "❌ Оплату не підтверджено.\n{detail}",
    },

    # --- Чек / квитанция ---
    "receipt.header": {"ru": "ДЕТАЛИ ЗАКАЗА", "en": "ORDER DETAILS", "ua": "ДЕТАЛІ ЗАМОВЛЕННЯ"},
    "receipt.date": {"ru": "Дата оформления", "en": "Date", "ua": "Дата оформлення"},
    "receipt.item": {"ru": "Наименование", "en": "Item", "ua": "Найменування"},
    "receipt.recipient": {"ru": "Получатель", "en": "Recipient", "ua": "Отримувач"},
    "receipt.price": {"ru": "Итоговая стоимость", "en": "Total price", "ua": "Підсумкова вартість"},
    "receipt.status_pending": {"ru": "Ожидает оплаты", "en": "Awaiting payment", "ua": "Очікує оплати"},

    # --- Заказы ---
    "orders.empty": {
        "ru": "У вас пока нет оформленных заказов.",
        "en": "You have no orders yet.",
        "ua": "У вас ще немає оформлених замовлень.",
    },
    "orders.history": {
        "ru": "История ваших последних заказов:",
        "en": "Your recent order history:",
        "ua": "Історія ваших останніх замовлень:",
    },
    "orders.item_order": {"ru": "Заказ", "en": "Order", "ua": "Замовлення"},
    "orders.item_product": {"ru": "Товар", "en": "Product", "ua": "Товар"},
    "orders.item_sum": {"ru": "Сумма", "en": "Amount", "ua": "Сума"},
    "orders.item_status": {"ru": "Статус", "en": "Status", "ua": "Статус"},
    "orders.item_date": {"ru": "Дата", "en": "Date", "ua": "Дата"},

    # Человекочитаемые названия статусов заказа (используются вместе с ORDER_STATUS_EMOJI
    # через order_status_label(status, lang), чтобы статус выглядел одинаково
    # везде: "Мои заказы", /status, уведомления).
    "status.НОВЫЙ": {"ru": "Новый", "en": "New", "ua": "Новий"},
    "status.ОЖИДАНИЕ_ОПЛАТЫ": {"ru": "Ожидает оплаты", "en": "Awaiting payment", "ua": "Очікує оплати"},
    "status.НА_ПРОВЕРКЕ": {"ru": "На проверке", "en": "Under review", "ua": "На перевірці"},
    "status.НА_РАССМОТРЕНИИ": {"ru": "На рассмотрении", "en": "Being processed", "ua": "На розгляді"},
    "status.ВЫПОЛНЕН": {"ru": "Выполнен", "en": "Completed", "ua": "Виконано"},
    "status.ОТКЛОНЕН": {"ru": "Отклонён", "en": "Rejected", "ua": "Відхилено"},

    # --- Поддержка ---
    "support.enter": {
        "ru": (
            "Вы вошли в чат техподдержки. Все ваши последующие сообщения будут сразу отправлены администратору.\n\n"
            "Когда ваш вопрос будет полностью решен, нажмите на кнопку под этим сообщением:"
        ),
        "en": (
            "You have entered the support chat. All your subsequent messages will be forwarded to an admin.\n\n"
            "Once your issue is resolved, tap the button below:"
        ),
        "ua": (
            "Ви увійшли в чат технічної підтримки. Усі ваші подальші повідомлення будуть одразу надсилатися адміністратору.\n\n"
            "Коли ваше питання буде повністю вирішене, натисніть кнопку нижче:"
        ),
    },
    "support.exit": {
        "ru": "Диалог поддержки закрыт. Вы вернулись в главное меню магазина.",
        "en": "Support chat closed. You're back in the main menu.",
        "ua": "Діалог підтримки закрито. Ви повернулися до головного меню магазину.",
    },
    "support.sent": {
        "ru": "Ваше сообщение доставлено оператору. Вы можете продолжать писать сюда.",
        "en": "Your message has been delivered to the operator. You can keep writing here.",
        "ua": "Ваше повідомлення доставлено оператору. Ви можете продовжувати писати сюди.",
    },

    # --- Отзывы ---
    "reviews.text": {
        "ru": "Канал с отзывами наших клиентов:\n{link}",
        "en": "Customer reviews channel:\n{link}",
        "ua": "Канал з відгуками наших клієнтів:\n{link}",
    },

    # --- Статус заказов (для уведомлений) ---
    "order.cancelled": {
        "ru": "Заказ #{order_id} переведен в статус ОТКЛОНЕН.",
        "en": "Order #{order_id} has been cancelled.",
        "ua": "Замовлення #{order_id} переведено в статус ВІДХИЛЕНО.",
    },
    "order.paid_notify": {
        "ru": "🎉 Ваш заказ #{order_num} успешно оплачен! Звезды/Premium будут доставлены в ближайшее время.",
        "en": "🎉 Your order #{order_num} has been paid! Stars/Premium will be delivered shortly.",
        "ua": "🎉 Ваше замовлення #{order_num} успішно оплачено! Зірки/Premium буде доставлено найближчим часом.",
    },

    # --- Верификация чека ---
    "proof.choose": {
        "ru": "Верификация перевода\n\nВыберите способ отправки квитанции:",
        "en": "Payment verification\n\nChoose how to send your receipt:",
        "ua": "Верифікація переказу\n\nОберіть спосіб надсилання квитанції:",
    },
    "proof.send_photo": {
        "ru": "Отправьте скриншот оплаты как обычное фото:",
        "en": "Send a screenshot of the payment as a regular photo:",
        "ua": "Надішліть скриншот оплати як звичайне фото:",
    },
    "proof.send_pdf": {
        "ru": "Отправьте квитанцию (PDF) как файл/документ:",
        "en": "Send the receipt (PDF) as a file/document:",
        "ua": "Надішліть квитанцію (PDF) як файл/документ:",
    },
    "proof.accepted": {
        "ru": "Ваш чек принят. Менеджер проверяет поступление средств.",
        "en": "Your receipt has been accepted. The manager is verifying the payment.",
        "ua": "Ваш чек прийнято. Менеджер перевіряє надходження коштів.",
    },

    # --- Реферал ---
    "ref.new_referral": {
        "ru": "🤝 У вас новый реферал! Пользователь @{username} присоединился по вашей ссылке. Когда он оплатит первый заказ, вам начислится бонус на баланс.",
        "en": "🤝 You have a new referral! User @{username} joined via your link. When they complete their first order, you'll receive a bonus.",
        "ua": "🤝 У вас новий реферал! Користувач @{username} приєднався за вашим посиланням. Коли він оплатить перше замовлення, вам нарахується бонус.",
    },
    "ref.refresh_done": {"ru": "Обновлено", "en": "Updated", "ua": "Оновлено"},
    "ref.usage_alert": {
        "ru": "Напишите в поддержку перед оплатой заказа — оператор применит скидку с вашего баланса вручную.",
        "en": "Message support before paying — the operator will apply your balance as a discount manually.",
        "ua": "Напишіть у підтримку перед оплатою — оператор застосує знижку з вашого балансу вручну.",
    },

    # --- Настройки языка ---
    "lang.switched": {
        "ru": "✅ Язык переключен на Русский.",
        "en": "✅ Language switched to English.",
        "ua": "✅ Мову змінено на Українську.",
    },

    # --- Пользовательские покупки (site payload) ---
    "site.stars_username": {
        "ru": "Введите @username получателя звезд:",
        "en": "Enter the @username of the star recipient:",
        "ua": "Введіть @username отримувача зірок:",
    },
    "site.prem_choose": {
        "ru": "Выберите способ оформления Premium:",
        "en": "Choose how to set up Premium:",
        "ua": "Оберіть спосіб оформлення Premium:",
    },
    "site.prem_login_via_site": {
        "ru": "🔑 Вы выбрали Premium «со входом» через сайт. Опишите, на какой срок — оператор свяжется с вами лично.",
        "en": "🔑 You chose Premium «with login» via the website. Tell us the desired duration — an operator will contact you personally.",
        "ua": "🔑 Ви обрали Premium «зі входом» через сайт. Опишіть бажаний термін — оператор зв'яжеться з вами особисто.",
    },

    # --- Уведомления пользователям ---
    "notify.review": {
        "ru": "Ваш заказ на рассмотрении.",
        "en": "Your order is under review.",
        "ua": "Ваше замовлення на розгляді.",
    },
    "notify.rejected": {
        "ru": "Ваш платеж отклонен. Пожалуйста, свяжитесь с поддержкой.",
        "en": "Your payment was rejected. Please contact support.",
        "ua": "Ваш платіж відхилено. Будь ласка, зверніться до підтримки.",
    },
    "notify.completed": {
        "ru": "Ваш заказ подтвержден как выполнен, звезды доставлены! Напишите, пожалуйста, отзыв в @StarlifyAdmin",
        "en": "Your order has been confirmed as completed, stars delivered! Please leave a review at @StarlifyAdmin",
        "ua": "Ваше замовлення підтверджено як виконане, зірки доставлено! Напишіть, будь ласка, відгук в @StarlifyAdmin",
    },
    "notify.support_reply": {
        "ru": "✉️ Ответ от поддержки:\n\n{text}\n\n<i>Вы можете продолжать диалог здесь. Если вопрос решен, закройте его кнопкой ниже.</i>",
        "en": "✉️ Reply from support:\n\n{text}\n\n<i>You can continue the dialogue here. If your issue is resolved, close it with the button below.</i>",
        "ua": "✉️ Відповідь від підтримки:\n\n{text}\n\n<i>Ви можете продовжувати діалог тут. Якщо питання вирішено, закрийте його кнопкою нижче.</i>",
    },

    # --- Донаты / поддержка проекта ---
    "donate.intro": {
        "ru": "💖 Спасибо, что хотите поддержать проект!\n\nВыберите удобный способ:",
        "en": "💖 Thanks for wanting to support the project!\n\nChoose a payment method:",
        "ua": "💖 Дякуємо, що хочете підтримати проєкт!\n\nОберіть зручний спосіб:",
    },
    "donate.stars_choose": {
        "ru": "⭐ Выберите количество Stars для доната или введите своё:",
        "en": "⭐ Choose how many Stars to donate, or enter a custom amount:",
        "ua": "⭐ Оберіть кількість Stars для донату або введіть своє значення:",
    },
    "donate.stars_custom_prompt": {
        "ru": "✏️ Введите количество Stars (число от 1 до 100000):",
        "en": "✏️ Enter the number of Stars (1 to 100000):",
        "ua": "✏️ Введіть кількість Stars (число від 1 до 100000):",
    },
    "donate.stars_invalid": {
        "ru": "❌ Некорректное число. Введите целое число от 1 до 100000.",
        "en": "❌ Invalid number. Enter a whole number from 1 to 100000.",
        "ua": "❌ Некоректне число. Введіть ціле число від 1 до 100000.",
    },
    "donate.stars_invoice_title": {
        "ru": "Поддержка проекта",
        "en": "Support the project",
        "ua": "Підтримка проєкту",
    },
    "donate.stars_invoice_desc": {
        "ru": "Донат {amount} ⭐ Stars в поддержку {company}. Спасибо!",
        "en": "A donation of {amount} ⭐ Stars to support {company}. Thank you!",
        "ua": "Донат {amount} ⭐ Stars на підтримку {company}. Дякуємо!",
    },
    "donate.stars_thanks": {
        "ru": "🎉 Спасибо огромное за поддержку в {amount} ⭐ Stars! Это очень помогает проекту развиваться.",
        "en": "🎉 Thank you so much for your support of {amount} ⭐ Stars! It really helps the project grow.",
        "ua": "🎉 Дуже дякуємо за підтримку в {amount} ⭐ Stars! Це дуже допомагає проєкту розвиватися.",
    },
    "donate.crypto_choose": {
        "ru": "🪙 Оплата в TON / USDT через CryptoBot.\n\nВыберите сумму доната (в $) или введите свою:",
        "en": "🪙 Pay in TON / USDT via CryptoBot.\n\nChoose a donation amount (in $) or enter a custom one:",
        "ua": "🪙 Оплата в TON / USDT через CryptoBot.\n\nОберіть суму донату (в $) або введіть свою:",
    },
    "donate.crypto_custom_prompt": {
        "ru": "✏️ Введите сумму доната в долларах (от 1 до 10000):",
        "en": "✏️ Enter the donation amount in USD (1 to 10000):",
        "ua": "✏️ Введіть суму донату в доларах (від 1 до 10000):",
    },
    "donate.crypto_invalid": {
        "ru": "❌ Некорректная сумма. Введите число от 1 до 10000.",
        "en": "❌ Invalid amount. Enter a number from 1 to 10000.",
        "ua": "❌ Некоректна сума. Введіть число від 1 до 10000.",
    },
    "donate.crypto_creating": {
        "ru": "⏳ Создаю счёт на оплату...",
        "en": "⏳ Creating a payment invoice...",
        "ua": "⏳ Створюю рахунок на оплату...",
    },
    "donate.crypto_invoice_ready": {
        "ru": "🪙 Счёт на {amount} $ создан!\n\nОплатите по кнопке ниже (TON или USDT), а затем нажмите «✅ Я оплатил», чтобы я проверил платёж.",
        "en": "🪙 An invoice for ${amount} has been created!\n\nPay using the button below (TON or USDT), then tap “✅ I've paid” so I can verify the payment.",
        "ua": "🪙 Рахунок на {amount} $ створено!\n\nОплатіть за кнопкою нижче (TON або USDT), а потім натисніть «✅ Я оплатив», щоб я перевірив платіж.",
    },
    "donate.crypto_error": {
        "ru": "❌ Не удалось создать счёт: {error}\n\nПопробуйте позже или напишите в поддержку.",
        "en": "❌ Failed to create the invoice: {error}\n\nPlease try again later or contact support.",
        "ua": "❌ Не вдалося створити рахунок: {error}\n\nСпробуйте пізніше або зверніться в підтримку.",
    },
    "donate.crypto_not_paid": {
        "ru": "⏳ Платёж пока не найден. Если вы только что оплатили — подождите немного и нажмите проверку ещё раз.",
        "en": "⏳ Payment not found yet. If you just paid, wait a bit and check again.",
        "ua": "⏳ Платіж поки не знайдено. Якщо ви щойно оплатили — зачекайте трохи і перевірте ще раз.",
    },
    "donate.crypto_thanks": {
        "ru": "🎉 Спасибо огромное за донат {amount} $! Платёж подтверждён. Это очень помогает проекту.",
        "en": "🎉 Thank you so much for your ${amount} donation! Payment confirmed. It really helps the project.",
        "ua": "🎉 Дуже дякуємо за донат {amount} $! Платіж підтверджено. Це дуже допомагає проєкту.",
    },
    "donate.cancelled": {
        "ru": "❌ Донат отменён.",
        "en": "❌ Donation cancelled.",
        "ua": "❌ Донат скасовано.",
    },
    "notify.new_donation_stars": {
        "ru": "💖 Новый донат!\nОт: @{username} (ID: {tg_id})\nСумма: {amount} ⭐ Stars",
        "en": "💖 New donation!\nFrom: @{username} (ID: {tg_id})\nAmount: {amount} ⭐ Stars",
        "ua": "💖 Новий донат!\nВід: @{username} (ID: {tg_id})\nСума: {amount} ⭐ Stars",
    },
    "notify.new_donation_crypto": {
        "ru": "💖 Новый донат (CryptoBot)!\nОт: @{username} (ID: {tg_id})\nСумма: {amount} $",
        "en": "💖 New donation (CryptoBot)!\nFrom: @{username} (ID: {tg_id})\nAmount: ${amount}",
        "ua": "💖 Новий донат (CryptoBot)!\nВід: @{username} (ID: {tg_id})\nСума: {amount} $",
    },
}

LANG_NAMES = {"ru": "Русский 🇷🇺", "en": "English 🇬🇧", "ua": "Українська 🇺🇦"}

# Эмодзи по коду статуса — единая точка правды, чтобы не дублировать
# словарь status_emoji в нескольких местах main.py с риском разъехаться.
ORDER_STATUS_EMOJI = {
    "НОВЫЙ": "🆕",
    "ОЖИДАНИЕ_ОПЛАТЫ": "⏳",
    "НА_ПРОВЕРКЕ": "🔍",
    "НА_РАССМОТРЕНИИ": "🔄",
    "ВЫПОЛНЕН": "✅",
    "ОТКЛОНЕН": "❌",
}


def order_status_label(status, lang="ru"):
    """Возвращает '<эмодзи> <человекочитаемое название>' для статуса заказа
    на нужном языке, например 'ВЫПОЛНЕН' + 'en' -> '✅ Completed'.
    Если статус неизвестен — возвращает его как есть с эмодзи "❓".
    """
    emoji = ORDER_STATUS_EMOJI.get(status, "❓")
    label = t(f"status.{status}", lang) if f"status.{status}" in STRINGS else status
    return f"{emoji} {label}"


def t(key, lang="ru", **kwargs):
    """Возвращает локализованную строку. Если перевода нет — fallback на ru."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    text = entry.get(lang) or entry.get("ru") or ""
    if kwargs:
        text = text.format(**kwargs)
    return text


def all_variants(key):
    """Возвращает список переводов строки на всех языках (для матчинга кнопок)."""
    entry = STRINGS.get(key, {})
    return list(entry.values())

def all_menu_variants():
    """Возвращает все тексты кнопок главного меню на всех языках."""
    menu_keys = [
        "menu.buy_stars", "menu.buy_premium", "menu.profile", "menu.orders",
        "menu.referral", "menu.settings", "menu.support", "menu.reviews",
        "menu.shop", "menu.donate"
    ]
    result = set()
    for key in menu_keys:
        result.update(all_variants(key))
    return result
