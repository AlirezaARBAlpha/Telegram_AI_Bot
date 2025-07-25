# model_utils.py

# حافظهٔ مدل‌های کاربران
user_models = {}

# مدل پیش‌فرض
DEFAULT_MODEL = "tngtech/deepseek-r1t2-chimera:free"


def set_model(user_id: int, model_code: str):
    user_models[user_id] = model_code


def get_model(user_id: int) -> str:
    return user_models.get(user_id, None)


def get_model_or_default(user_id: int) -> str:
    return user_models.get(user_id, DEFAULT_MODEL)


def has_model(user_id: int) -> bool:
    return user_id in user_models
