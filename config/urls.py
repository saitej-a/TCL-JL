"""Root URL configuration. Phase 1.2 shipped the root status route + health
probes; Phase 2.2 adds the /api/v1/ auth, me, and account surface."""

from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("health/", views.health, name="health"),
    path("health/ready/", views.health_ready, name="health-ready"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls_auth")),
    path("api/v1/", include("apps.accounts.urls_account")),
]
