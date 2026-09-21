"""Auth API views (04 §12-18, §76-78; T2.4-T2.11).

``SpecErrorMixin`` routes every view's exceptions through
``accounts.exceptions.auth_exception_handler`` so responses carry the spec
envelopes (``INVALID_CREDENTIALS``, ``RATE_LIMITED`` + ``Retry-After``).
"""

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from apps.accounts.exceptions import auth_exception_handler
from apps.accounts.serializers import (
    DeleteAccountSerializer,
    FamilyTokenObtainPairSerializer,
    FamilyTokenRefreshSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserPrivateSerializer,
    VerifyEmailSerializer,
)
from apps.accounts.throttles import (
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegisterRateThrottle,
    VerifyResendRateThrottle,
)

REGISTRATION_MESSAGE = "Registration successful. Please check your email to activate your account."


class SpecErrorMixin:
    """Opt into the accounts error-envelope handler (exceptions.py)."""

    spec_error_envelopes = True

    def handle_exception(self, exc):
        context = self.get_exception_handler_context()
        response = auth_exception_handler(exc, context)
        if response is None:
            raise exc
        response.exception = True
        return response


class RegisterView(SpecErrorMixin, APIView):
    """POST /auth/register/ — 201 + identical body on all branches (D1)."""

    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]
    throttle_scope = "auth_register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.register_user(
            serializer.validated_data["email"],
            serializer.validated_data["password"],
        )
        return Response({"message": REGISTRATION_MESSAGE}, status=status.HTTP_201_CREATED)


class VerifyEmailView(SpecErrorMixin, APIView):
    """POST /auth/verification/verify/ — Option A token API (04 §13.2)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.verify_email(serializer.validated_data["token"])
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"message": "Email verified successfully."})


class ResendVerificationView(SpecErrorMixin, APIView):
    """POST /auth/verification/resend/ — generic body, 1/min (06 §2.5)."""

    permission_classes = [AllowAny]
    throttle_classes = [VerifyResendRateThrottle]
    throttle_scope = "auth_verify_resend"

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.resend_verification(serializer.validated_data["email"])
        return Response({"message": services.GENERIC_VERIFICATION_MESSAGE})


class LoginView(SpecErrorMixin, APIView):
    """POST /auth/login/ — generic INVALID_CREDENTIALS on any failure (04 §14)."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = FamilyTokenObtainPairSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)  # raises 401 → envelope
        return Response(serializer.validated_data)


class TokenRefreshView(SpecErrorMixin, APIView):
    """POST /auth/token/refresh/ — rotation + family reuse-detection (AUTH-04)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FamilyTokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class LogoutView(SpecErrorMixin, APIView):
    """POST /auth/logout/ — blacklist the submitted refresh token (04 §16)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
        except TokenError as exc:
            raise ValidationError({"refresh": "Invalid or expired token."}) from exc
        if str(token.payload.get("user_id")) != str(request.user.pk):
            raise ValidationError({"refresh": "Token does not belong to this account."})
        try:
            token.blacklist()
        except AttributeError:  # blacklist app missing — cannot happen here
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(SpecErrorMixin, APIView):
    """POST /auth/password-reset/request/ — generic 200 both branches (06 §3.5)."""

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]
    throttle_scope = "auth_password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response({"message": services.GENERIC_RESET_MESSAGE})


class PasswordResetConfirmView(SpecErrorMixin, APIView):
    """POST /auth/password-reset/confirm/ — full pipeline + token revocation."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.confirm_password_reset(
                serializer.validated_data["token"],
                serializer.validated_data["new_password"],
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return Response({"message": "Password reset successfully."})


class MeView(SpecErrorMixin, generics.RetrieveAPIView):
    """GET /me/ — self-only representation (04 §18, 06 §5.2)."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserPrivateSerializer

    def get_object(self):
        return self.request.user


class DeleteAccountView(SpecErrorMixin, APIView):
    """DELETE /account/ — password re-auth then anonymization protocol (06 §2.7)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["password"]):
            raise PermissionDenied("Invalid email or password.")  # generic 403
        services.anonymize_delete_account(request.user, serializer.validated_data["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)
