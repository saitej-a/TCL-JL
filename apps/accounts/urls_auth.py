"""Auth endpoint routes (04 §12-17; plan deliverable 2)."""

from django.urls import path

from apps.accounts import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("verification/verify/", views.VerifyEmailView.as_view(), name="auth-verify"),
    path("verification/resend/", views.ResendVerificationView.as_view(), name="auth-verify-resend"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("token/refresh/", views.TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path(
        "password-reset/request/",
        views.PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
]
