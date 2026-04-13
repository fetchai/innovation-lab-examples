from app.config.settings import get_settings


def health_payload() -> dict[str, str]:
    s = get_settings()
    return {"status": "ok", "env": s.app_env}
