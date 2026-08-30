# Rendered by YunoHost from conf/local_settings.py at install/upgrade time.
# Imported at the bottom of weddjango/settings.py — do not edit by hand,
# it will be overwritten on the next upgrade/config change.

from pathlib import Path

DATA_DIR = Path("__DATA_DIR__")

DEBUG = False

ALLOWED_HOSTS = ["__DOMAIN__"]

CSRF_TRUSTED_ORIGINS = ["https://__DOMAIN__"]

# nginx sets X-Forwarded-Proto (conf/nginx.conf) so Django knows the original
# request was HTTPS even though gunicorn only ever sees plain HTTP from it.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECRET_KEY_FILE = DATA_DIR / "secret.txt"
if not SECRET_KEY_FILE.exists():
    import secrets

    SECRET_KEY_FILE.write_text(secrets.token_urlsafe(64))
    SECRET_KEY_FILE.chmod(0o400)
SECRET_KEY = SECRET_KEY_FILE.read_text().strip()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

STATIC_ROOT = "__INSTALL_DIR__/static"
MEDIA_ROOT = "__INSTALL_DIR__/media"

SITE_DOMAIN = "https://__DOMAIN__"
