# config/settings.py

from config.credentials import DATABASE

class Settings:
    DB_HOST = DATABASE["HOST"]
    DB_NAME = DATABASE["NAME"]
    DB_USER = DATABASE["USER"]
    DB_PASSWORD = DATABASE["PASSWORD"]
    DB_PORT = DATABASE["PORT"]

    @staticmethod
    def validate():
        missing = []
        for key, value in DATABASE.items():
            if not value:
                missing.append(key)
        if missing:
            raise RuntimeError(
                f"Missing DB config values: {missing}"
            )
