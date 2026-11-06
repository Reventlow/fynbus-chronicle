"""Admin configuration for accounts app."""

from allauth.socialaccount.models import SocialAccount
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef
from django.utils import timezone
from django.utils.html import format_html

from .backends import is_break_glass
from .models import APIKey, LoginLog


class SSOLinkedFilter(admin.SimpleListFilter):
    """Filter users by whether they have signed in with Microsoft yet."""

    title = "Microsoft-login"
    parameter_name = "sso"

    def lookups(self, request, model_admin):
        return [("yes", "Tilknyttet"), ("no", "Ikke tilknyttet")]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(sso_linked=True)
        if self.value() == "no":
            return queryset.filter(sso_linked=False)
        return queryset


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django's user admin plus who is linked to Microsoft SSO.

    Before switching SSO_ONLY on, every active user except the break-glass
    accounts should show "Tilknyttet": they have signed in with Microsoft
    once, so their account is linked by Entra object id.
    """

    list_display = (*DjangoUserAdmin.list_display, "sso_badge", "last_login")
    list_filter = (*DjangoUserAdmin.list_filter, SSOLinkedFilter)

    def get_queryset(self, request):
        linked = SocialAccount.objects.filter(user=OuterRef("pk"), provider="microsoft")
        return super().get_queryset(request).annotate(sso_linked=Exists(linked))

    @admin.display(description="SSO", ordering="sso_linked")
    def sso_badge(self, obj):
        if is_break_glass(obj):
            return format_html('<span title="Må logge ind med adgangskode">{}</span>', "Break-glass")
        return "✓ Tilknyttet" if obj.sso_linked else "—"


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    """Read-only admin view for login/logout events."""

    list_display = ("timestamp", "user", "event", "ip_address")
    list_filter = ("event", "timestamp", "user")
    search_fields = ("user__username", "user__email", "ip_address")
    ordering = ("-timestamp",)
    readonly_fields = ("user", "event", "timestamp", "ip_address", "user_agent")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin view for API keys.

    Raw keys aren't recoverable (only the SHA-256 hash is stored). Admins
    can revoke keys but can't edit the hash directly. New keys must be
    minted via the user's self-service page or `manage.py mint_api_key`.
    """

    list_display = ("user", "label", "scope_badge", "prefix", "last_used_at", "status")
    list_filter = ("scope", "revoked_at", "user")
    search_fields = ("user__username", "user__email", "label", "prefix")
    ordering = ("-created_at",)
    readonly_fields = ("prefix", "hashed_key", "created_at", "last_used_at")
    fieldsets = (
        (None, {"fields": ("user", "label", "scope")}),
        (
            "Sikkerhed",
            {"fields": ("prefix", "hashed_key", "revoked_at")},
        ),
        (
            "Tidsstempler",
            {"fields": ("created_at", "last_used_at")},
        ),
    )
    actions = ("revoke_selected",)

    @admin.display(description="Adgang", ordering="scope")
    def scope_badge(self, obj: APIKey) -> str:
        color = "#286ed2" if obj.scope == APIKey.Scope.READ else "#b48438"
        return format_html(
            '<span style="background:{};color:white;padding:2px 7px;border-radius:4px;font-size:11px;">{}</span>',
            color,
            obj.get_scope_display(),
        )

    @admin.display(description="Status")
    def status(self, obj: APIKey) -> str:
        if obj.revoked_at:
            return format_html('<span style="color:#a33;">Tilbagekaldt</span>')
        return format_html('<span style="color:#3a7;">Aktiv</span>')

    @admin.action(description="Tilbagekald markerede nøgler")
    def revoke_selected(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f"{count} nøgle(r) tilbagekaldt.")

    def has_add_permission(self, request):
        # Force key creation through the self-service page or management
        # command so the raw key is shown once. Adding via admin would
        # leave it unrecoverable.
        return False
