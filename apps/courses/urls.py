"""URL configuration for Kursusmateriale (/kursus/)."""

from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.index, name="index"),
    path("fil/<str:key>/", views.material_file, name="file"),
    path("element/<str:key>/edit/", views.material_edit, name="material-edit"),
    path("element/<str:key>/delete/", views.material_delete, name="material-delete"),
    path("<slug:slug>/", views.folder, name="folder"),
    path("<slug:slug>/edit/", views.folder_edit, name="folder-edit"),
    path("<slug:slug>/delete/", views.folder_delete, name="folder-delete"),
    path("<slug:slug>/add/", views.material_add, name="material-add"),
]
