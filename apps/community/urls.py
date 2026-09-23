"""Community routes (Phase 5.2): /api/v1/community/ + /api/v1/comments/{id}/.

Identifier segments are `<str:pk>`, **not** `<uuid:pk>` (a deliberate F3 fix
for this surface): the uuid converter would 404 malformed strings at the Django
level, outside the project envelope. With `str`, the view's `_clean_uuid`
parses and renders the JSON `post_not_found`/`comment_not_found` envelope.
"""

from django.urls import path

from apps.community.views import (
    AnnouncementDetailView,
    AnnouncementListCreateView,
    AnnouncementPublishView,
    CommentDetailView,
    CommentListCreateView,
    PostDetailView,
    PostListCreateView,
    PostLockView,
    PostPinView,
    PostVoteView,
)

urlpatterns = [
    path("community/posts/", PostListCreateView.as_view(), name="community-post-list"),
    path(
        "community/posts/<str:pk>/",
        PostDetailView.as_view(),
        name="community-post-detail",
    ),
    path(
        "community/posts/<str:pk>/vote/",
        PostVoteView.as_view(),
        name="community-post-vote",
    ),
    path(
        "community/posts/<str:pk>/comments/",
        CommentListCreateView.as_view(),
        name="community-post-comments",
    ),
    path(
        "community/posts/<str:pk>/lock/",
        PostLockView.as_view(),
        name="community-post-lock",
    ),
    path(
        "community/posts/<str:pk>/pin/",
        PostPinView.as_view(),
        name="community-post-pin",
    ),
    path(
        "community/comments/<str:pk>/",
        CommentDetailView.as_view(),
        name="community-comment-detail",
    ),
    # Announcements (Phase 8.2 — 04 §71): public read, staff write.
    path("announcements/", AnnouncementListCreateView.as_view(), name="announcement-list"),
    path(
        "announcements/<str:pk>/",
        AnnouncementDetailView.as_view(),
        name="announcement-detail",
    ),
    path(
        "announcements/<str:pk>/publish/",
        AnnouncementPublishView.as_view(),
        name="announcement-publish",
    ),
]
