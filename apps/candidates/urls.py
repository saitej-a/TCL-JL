"""Profile API routes (Phase 3.2): owner profile + public candidate lookup."""

from django.urls import path

from apps.candidates.views import ProfileView, PublicCandidateView

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("candidates/<uuid:pk>/", PublicCandidateView.as_view(), name="public-candidate"),
]
