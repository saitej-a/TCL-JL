"""Account-surface routes (04 §18, §78): current user + deletion."""

from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("me/", views.MeView.as_view(), name="me"),
    path("account/", views.DeleteAccountView.as_view(), name="account-delete"),
]
