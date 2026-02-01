"""
Development-specific Django settings for FynBus Chronicle.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# Development-specific apps
# INSTALLED_APPS += [  # noqa: F405
#     "debug_toolbar",
# ]

# MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

# Debug toolbar settings (disabled due to JS conflicts with HTMX/Alpine)
# INTERNAL_IPS = ["127.0.0.1", "::1", "localhost"]
# DEBUG_TOOLBAR_CONFIG = {
#     "SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG,
# }

# Use console email backend in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable password validation in development for easier testing
AUTH_PASSWORD_VALIDATORS = []

# Session settings for development
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = False  # Allow cookies over HTTP in development
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"
