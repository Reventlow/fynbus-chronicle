"""
Base Django settings for FynBus Chronicle.

Settings common to all environments. Environment-specific settings
are in dev.py and prod.py.
"""

from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security settings
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost", cast=Csv())

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.microsoft",
    "django_htmx",
]

LOCAL_APPS = [
    "apps.logbook",
    "apps.accounts",
    "apps.dashboard",
    "apps.oncall",
    "apps.tasks",
    "apps.api",
    "apps.feedback",
    "apps.cves",
    "apps.themes",
    "apps.notifications",
    "apps.reports",
    "apps.images",
    "apps.planner",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "chronicle.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "chronicle.context_processors.version",
                "chronicle.context_processors.active_theme",
                "chronicle.context_processors.star_wars_day",
                "chronicle.context_processors.read_only_friday",
                "chronicle.context_processors.touch_grass_weekend",
                "apps.accounts.context_processors.editor_context",
                "apps.feedback.context_processors.feedback_badge",
                "apps.notifications.context_processors.notifications_badge",
                "apps.planner.context_processors.planner_nav",
            ],
        },
    },
]

WSGI_APPLICATION = "chronicle.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
# Override in dev.py or prod.py for specific database configurations

# Database - supports both SQLite and PostgreSQL via DATABASE_URL
DATABASE_URL = config("DATABASE_URL", default="")

if DATABASE_URL:
    # PostgreSQL via DATABASE_URL
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL)
    }
else:
    # SQLite (default for development and simple deployments)
    # In Docker, use /app/data/ for persistence
    SQLITE_DIR = config("SQLITE_DIR", default=str(BASE_DIR))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(SQLITE_DIR) / "db.sqlite3",
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "da-dk"
TIME_ZONE = "Europe/Copenhagen"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Files attached to reports (videos). Lives beside the SQLite database so it
# sits on the persisted /app/data volume in Docker; served by a Django view,
# never as static media.
REPORT_FILES_DIR = Path(config("REPORT_FILES_DIR", default=str(Path(config("SQLITE_DIR", default=str(BASE_DIR))) / "report_files")))
# Images pasted into descriptions (tasks, feature requests). Same reasoning:
# persisted volume, served by a login-gated view.
IMAGE_FILES_DIR = Path(config("IMAGE_FILES_DIR", default=str(Path(config("SQLITE_DIR", default=str(BASE_DIR))) / "image_files")))
# PDFs attached to CVEs (e.g. FE-CSIRT advisories). Same rule as images:
# beside the database on the persisted volume, served only by a login-gated view.
CVE_FILES_DIR = Path(config("CVE_FILES_DIR", default=str(Path(config("SQLITE_DIR", default=str(BASE_DIR))) / "cve_files")))
CVE_ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sites framework (required by allauth)
SITE_ID = 1

# Authentication backends
# Django's and allauth's password backends, wrapped so that SSO_ONLY can
# refuse passwords (apps/accounts/backends.py).
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.PasswordBackend",
    "apps.accounts.backends.AllauthPasswordBackend",
]

# How long a login lasts. Django's default is two weeks; a working day
# (e.g. 12) means a user disabled in Entra loses access by the next day.
SESSION_COOKIE_AGE = config("SESSION_MAX_HOURS", default=336, cast=int) * 3600

# django-allauth settings (updated for allauth 0.61+)
ACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Who may get an account: self sign-up is closed, and SSO admits only
# FynBus accounts (see apps/accounts/adapters.py).
ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
# Never match a Microsoft login to a user by e-mail on allauth's own; the
# adapter makes that link once, under its own rules.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False

# Office 365 SSO Configuration
SSO_ENABLED = config("SSO_ENABLED", default=False, cast=bool)
MICROSOFT_CLIENT_ID = config("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = config("MICROSOFT_CLIENT_SECRET", default="")
# The FynBus tenant GUID. No "common" fallback: with SSO on, "common" would
# let any Microsoft account, from any organisation, sign in.
MICROSOFT_TENANT_ID = config("MICROSOFT_TENANT_ID", default="")
# SSO may use its own app registration (recommended: one without the
# Mail.Send permission the Graph mail backend needs). Falls back to the
# shared MICROSOFT_CLIENT_ID / _SECRET.
SSO_CLIENT_ID = config("SSO_CLIENT_ID", default="") or MICROSOFT_CLIENT_ID
SSO_CLIENT_SECRET = config("SSO_CLIENT_SECRET", default="") or MICROSOFT_CLIENT_SECRET
SSO_ALLOWED_EMAIL_DOMAINS = config("SSO_ALLOWED_EMAIL_DOMAINS", default="fynbus.dk", cast=Csv())
SSO_ALLOW_GUESTS = config("SSO_ALLOW_GUESTS", default=False, cast=bool)
# A FynBus account without a Chronicle user gets one, read-only (Viewer).
SSO_AUTO_CREATE_USERS = config("SSO_AUTO_CREATE_USERS", default=True, cast=bool)
# Microsoft sign-in only: passwords are refused except for the break-glass
# accounts below (usernames), kept for when Entra is unavailable. Their
# form is at /accounts/login/?local=1. See apps/accounts/backends.py.
SSO_ONLY = config("SSO_ONLY", default=False, cast=bool)
SSO_BREAK_GLASS_USERS = config("SSO_BREAK_GLASS_USERS", default="", cast=Csv())
if SSO_ONLY and not SSO_ENABLED:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("SSO_ONLY=True needs SSO_ENABLED=True, or nobody could log in.")

if SSO_ENABLED:
    import re as _re

    from django.core.exceptions import ImproperlyConfigured

    if not SSO_CLIENT_ID or not SSO_CLIENT_SECRET:
        raise ImproperlyConfigured("SSO_ENABLED needs SSO_CLIENT_ID/SECRET (or MICROSOFT_CLIENT_ID/SECRET).")
    if not _re.fullmatch(r"[0-9a-fA-F-]{36}", MICROSOFT_TENANT_ID):
        raise ImproperlyConfigured(
            "SSO_ENABLED needs MICROSOFT_TENANT_ID set to the tenant GUID "
            "(not 'common', 'organizations' or a domain)."
        )
    SOCIALACCOUNT_PROVIDERS = {
        "microsoft": {
            "APP": {
                "client_id": SSO_CLIENT_ID,
                "secret": SSO_CLIENT_SECRET,
            },
            "TENANT": MICROSOFT_TENANT_ID,
            "SCOPE": ["openid", "email", "profile", "User.Read"],
        }
    }

# MS Planner board (apps/planner, docs/PLANNER.md). The web container shows
# the mirror and seals sign-ins with the public key; only the sync container
# has the client secret and the private key, and only it talks to Graph.
PLANNER_ENABLED = config("PLANNER_ENABLED", default=False, cast=bool)
PLANNER_SYNC_ENABLED = config("PLANNER_SYNC_ENABLED", default=False, cast=bool)
PLANNER_TENANT_ID = config("PLANNER_TENANT_ID", default="") or MICROSOFT_TENANT_ID
PLANNER_CLIENT_ID = config("PLANNER_CLIENT_ID", default="")
PLANNER_CLIENT_SECRET = config("PLANNER_CLIENT_SECRET", default="")  # sync container only
PLANNER_PLAN_ID = config("PLANNER_PLAN_ID", default="")
# The account allowed to be connected (e.g. SVC-Chronicle-Planner@fynbus.dk);
# any other account is refused when it signs in.
PLANNER_SERVICE_ACCOUNT = config("PLANNER_SERVICE_ACCOUNT", default="")
PLANNER_PUBLIC_KEY = config("PLANNER_PUBLIC_KEY", default="")
PLANNER_PRIVATE_KEY = config("PLANNER_PRIVATE_KEY", default="")  # sync container only
# Must match the app registration's redirect URI exactly; empty = built
# from the request.
PLANNER_REDIRECT_URI = config("PLANNER_REDIRECT_URI", default="")
# Sync schedule (Europe/Copenhagen): often in working hours, rarely outside.
PLANNER_WORK_HOURS = config("PLANNER_WORK_HOURS", default="mon-fri 07:15-17:30")
PLANNER_INTERVAL_WORK = config("PLANNER_INTERVAL_WORK", default=120, cast=int)
PLANNER_INTERVAL_OFF = config("PLANNER_INTERVAL_OFF", default=900, cast=int)
# Changes on the board (complete, move, add, link) are made with each
# editor's own Microsoft sign-in. Off: the board is read-only for everyone.
PLANNER_WRITES_ENABLED = config("PLANNER_WRITES_ENABLED", default=True, cast=bool)
# Labels put on a card when it is linked to a Chronicle priority or case;
# created in the plan (first free label slot) if no label has the name.
PLANNER_LABEL_PRIORITY = config("PLANNER_LABEL_PRIORITY", default="Prioriteret opgave")
PLANNER_LABEL_CASE = config("PLANNER_LABEL_CASE", default="Sag")

# Email configuration
EMAIL_USE_GRAPH = config("EMAIL_USE_GRAPH", default=False, cast=bool)

if EMAIL_USE_GRAPH:
    EMAIL_BACKEND = "chronicle.email_backends.graph.GraphEmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="it@fynbus.dk")
CHRONICLE_EMAIL_RECIPIENTS = config("CHRONICLE_EMAIL_RECIPIENTS", default="", cast=Csv())

# Security settings (override in prod.py)
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# ServiceDesk Plus Integration
SERVICEDESK_URL = config("SERVICEDESK_URL", default="")
SERVICEDESK_API_KEY = config("SERVICEDESK_API_KEY", default="")
SERVICEDESK_SYNC_ENABLED = config("SERVICEDESK_SYNC_ENABLED", default=False, cast=bool)
SERVICEDESK_SYNC_INTERVAL = config("SERVICEDESK_SYNC_INTERVAL", default=300, cast=int)
