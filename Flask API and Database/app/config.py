import os

DEFAULTS = {
    "DATABASE_URL": "sqlite:///waste_sorting.db",   # use mysql+pymysql
    "REGION": "Dortmund",
    "MIN_CONFIDENCE": 0.35,
    "MAX_UPLOAD_MB": 8,
    "KICONNECT_API_KEY": "",
    "KICONNECT_MODEL": "GPT-OSS-120B",
}


def load_config(overrides=None):
    config = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        env = os.environ.get(key)
        if env is not None:
            config[key] = type(default)(env) if isinstance(default, (int, float)) else env
    config.update(overrides or {})
    config["MAX_CONTENT_LENGTH"] = int(config["MAX_UPLOAD_MB"]) * 1024 * 1024
    return config
