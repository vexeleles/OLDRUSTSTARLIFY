from aiogram.fsm.state import State, StatesGroup

class BuyStars(StatesGroup):
    get_count = State()
    get_username = State()

class BuyPremium(StatesGroup):
    get_username = State()

class PaymentState(StatesGroup):
    select_proof_type = State()
    upload_photo = State()
    upload_pdf = State()

class SupportState(StatesGroup):
    active_chat = State()

class AdminSettings(StatesGroup):
    change_value = State()

class AdminBroadcast(StatesGroup):
    get_content = State()

class DonateState(StatesGroup):
    get_stars_amount = State()
    get_crypto_amount = State()