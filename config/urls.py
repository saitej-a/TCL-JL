"""Root URL configuration. Phase 1.2 shipped the root status route + health
probes; Phase 2.2 adds the /api/v1/ auth, me, and account surface; Phase 3.2
adds the profile + public candidate surface; Phase 4.2 adds the timeline CRUD
and dashboard surface; Phase 5.2 adds the community feed/comments/votes; Phase 7.2
adds the anonymous analytics reads and the public landing counters; Phase 8.1 adds the
authenticated candidate reporting surface under apps.moderation.
"""

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
    path("api/v1/", include("apps.candidates.urls")),
    path("api/v1/", include("apps.timeline.urls")),
    path("api/v1/", include("apps.community.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.moderation.urls")),
    path("api/v1/", include("apps.analytics.urls")),
]
