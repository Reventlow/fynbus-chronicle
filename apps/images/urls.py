"""URL configuration for pasted images. Both views require login."""

from django.urls import path

from . import views

app_name = "images"

urlpatterns = [
    path("", views.upload, name="upload"),
    path("preview/", views.preview, name="preview"),
    path("<str:key>/", views.view, name="view"),
]
