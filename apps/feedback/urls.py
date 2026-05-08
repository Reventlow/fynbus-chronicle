"""URL configuration for the feedback (feature requests) app."""

from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("", views.board, name="board"),
    path("new/", views.FeatureRequestCreateView.as_view(), name="create"),
    path("<int:pk>/", views.FeatureRequestDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.FeatureRequestUpdateView.as_view(), name="edit"),
    path("<int:pk>/solve/", views.mark_solved, name="solve"),
    path("<int:pk>/reopen/", views.reopen, name="reopen"),
    path("reorder/", views.reorder, name="reorder"),
    path("partials/nav-badge/", views.nav_badge, name="partial-nav-badge"),
]
