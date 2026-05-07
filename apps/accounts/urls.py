"""URL configuration for the accounts application."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("api-keys/", views.api_keys_list, name="api-keys"),
    path("api-keys/create/", views.api_keys_create, name="api-keys-create"),
    path("api-keys/<int:key_id>/revoke/", views.api_keys_revoke, name="api-keys-revoke"),
    path("api-keys/<int:key_id>/reroll/", views.api_keys_reroll, name="api-keys-reroll"),
]
