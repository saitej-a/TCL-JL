"""Timeline & dashboard API views (T4.4-T4.8; 4.2 D1-D3; 04 §24-§28).

Error bodies follow the 2.2/3.2 convention: serializer field-validation failures
render DRF's field-error shape untouched; service- and permission-level
rejections (`400` illegal transition, `404` missing profile/event, `405`) render
the project ``{"error": {code, message}}`` envelope through the accounts handler.

Two deliberate surface restrictions:

* **No detail read.** 04 §24 specifies collection GET, POST, and ``PATCH``/``DELETE
  /{id}/`` — no ``GET /{id}/`` — so it returns 405 rather than an invented route.
* **No PUT.** 04 §26 is a PATCH-style partial update; a full-replace PUT is not
  part of the surface (4.1 D2's forward-only semantics make a blind replace
  meaningless anyway).

IDOR defense is layered (06 §4.2): every queryset is scoped to ``request.user``
**and** ``IsTimelineOwner`` guards the object. A foreign UUID and a nonexistent
UUID are indistinguishable — same status, same code, same message — so the
endpoint leaks nothing about which identifiers exist (04 §89).
"""

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, MethodNotAllowed
from rest_framework.generics import GenericAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsVerified
from apps.accounts.views import SpecErrorMixin
from apps.candidates.models import CandidateProfile
from apps.candidates.permissions import IsActive
from apps.candidates.services import InvalidTransitionError
from apps.timeline.models import TimelineEvent
from apps.timeline.permissions import IsTimelineOwner
from apps.timeline.serializers import TimelineEventSerializer, TimelineEventWriteSerializer
from apps.timeline.services import (
    build_dashboard_payload,
    delete_timeline_event,
    record_timeline_event,
    update_timeline_event,
)


class _TransitionRejected(APIException):
    """Blocked status sync rendered as the 400 envelope (4.1 R3 codes pass through)."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, code: str):
        super().__init__({"error": {"code": code, "message": message}})


class _ProfileNotFound(APIException):
    """Same body as 3.2's profile route: a verified user without an onboarding
    profile is told to create one, not handed an empty timeline."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self):
        super().__init__(
            {
                "error": {
                    "code": "profile_not_found",
                    "message": "No candidate profile exists for this account.",
                }
            }
        )


class _EventNotFound(APIException):
    """Foreign **and** nonexistent UUIDs both land here, byte-identically (04 §89)."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self):
        super().__init__(
            {"error": {"code": "timeline_event_not_found", "message": "Timeline event not found."}}
        )


class _InvalidEventType(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, value):
        super().__init__(
            {
                "error": {
                    "code": "invalid_event_type",
                    "message": f"Unknown event_type filter value: {value!r}.",
                }
            }
        )


def _method_not_allowed(method: str, hint: str) -> MethodNotAllowed:
    return MethodNotAllowed(
        method,
        detail={"error": {"code": "method_not_allowed", "message": hint}},
    )


class TimelineErrorMixin(SpecErrorMixin):
    """Translate service/Django exceptions into the envelope, then let the
    accounts handler render them (3.2 precedent — one body style everywhere)."""

    def handle_exception(self, exc):
        if isinstance(exc, InvalidTransitionError):
            exc = _TransitionRejected(str(exc), code=exc.code)
        elif isinstance(exc, Http404):
            exc = _EventNotFound()
        return super().handle_exception(exc)

    def _get_profile(self) -> CandidateProfile:
        profile = getattr(self.request.user, "candidate_profile", None)
        if profile is None:
            raise _ProfileNotFound()
        return profile


class TimelineEventListCreateView(TimelineErrorMixin, ListCreateAPIView):
    """`/api/v1/timeline/` — the owner's own milestones only (04 §24-§25, T4.4-T4.5).

    Pagination is the global `PageNumberPagination` @ `PAGE_SIZE = 20`; because
    `page_size_query_param` is unset, a client-supplied `?page_size=100000` is
    ignored — 04 §9's "controlled maximum" without extra config. Ordering is
    `Meta.ordering` (newest first), so no client-supplied `?ordering=`.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    serializer_class = TimelineEventSerializer

    def get_queryset(self):
        # Layer 1 of the IDOR defense: scope in the query, never `objects.get(id=...)`.
        queryset = TimelineEvent.objects.filter(candidate__user=self.request.user)
        event_type = self.request.query_params.get("event_type")
        if event_type:
            if event_type not in TimelineEvent.EventType.values:
                raise _InvalidEventType(event_type)
            queryset = queryset.filter(event_type=event_type)
        return queryset

    def list(self, request, *args, **kwargs):
        # A verified user without a profile has no timeline to show: say so (3.2's
        # envelope) rather than rendering `{"count": 0}` for a candidate who
        # simply hasn't onboarded yet.
        self._get_profile()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        profile = self._get_profile()
        serializer = TimelineEventWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # R4: sync is not client-controllable — a caller must not be able to
        # record a milestone while leaving current_status stale (04 §121).
        event = record_timeline_event(profile, **serializer.validated_data)
        return Response(TimelineEventSerializer(event).data, status=status.HTTP_201_CREATED)


class TimelineEventDetailView(TimelineErrorMixin, GenericAPIView):
    """`/api/v1/timeline/{event_id}/` — PATCH/DELETE own events (04 §26-§27, T4.6).

    Deliberately not a ``RetrieveUpdateDestroyAPIView``: 04 §24 defines no detail
    read, so there is no ``get`` handler at all and ``http_method_names`` keeps
    PUT/POST out. Anything else 405s through the project envelope.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified, IsTimelineOwner]
    serializer_class = TimelineEventSerializer
    http_method_names = ["patch", "delete", "head", "options"]

    def http_method_not_allowed(self, request, *args, **kwargs):
        raise _method_not_allowed(
            request.method,
            f"{request.method} is not allowed here. Timeline events support PATCH "
            "and DELETE; the collection route lists the owner's events.",
        )

    def get_queryset(self):
        # Layer 1 again: foreign UUIDs simply don't resolve, so they 404 exactly
        # like nonexistent ones.
        return TimelineEvent.objects.filter(candidate__user=self.request.user)

    def patch(self, request, *args, **kwargs):
        event = self.get_object()
        serializer = TimelineEventWriteSerializer(event, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        event = update_timeline_event(event, dict(serializer.validated_data))
        return Response(TimelineEventSerializer(event).data)

    def delete(self, request, *args, **kwargs):
        event = self.get_object()
        delete_timeline_event(event)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardView(TimelineErrorMixin, APIView):
    """`/api/v1/dashboard/` — 04 §28 aggregate for the owner's home screen (T4.8).

    Shape and aggregation live in `services.build_dashboard_payload` so the
    payload has exactly one definition; Phases 6/7 fill in the notification and
    richer analytics blocks without touching this view.
    """

    permission_classes = [IsAuthenticated, IsActive, IsVerified]
    http_method_names = ["get", "head", "options"]

    def http_method_not_allowed(self, request, *args, **kwargs):
        raise _method_not_allowed(
            request.method, f"{request.method} is not allowed here. The dashboard is read-only."
        )

    def get(self, request):
        return Response(build_dashboard_payload(self._get_profile()))
