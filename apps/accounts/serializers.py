"""Auth serializers (04 §12-18, 06 §2-3).

Family reuse-detection (plan §1.3): login issues refresh tokens carrying a
random ``fam`` claim (token family id); :class:`FamilyTokenRefreshSerializer`
revokes every outstanding token of that family when a rotated token is
replayed (AUTH-04 headline criterion).
"""

from uuid import uuid4

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User


class UserPrivateSerializer(serializers.ModelSerializer):
    """Self-only representation (06 §5.2). Never exposes credentials."""

    profile_completed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "is_verified", "created_at", "profile_completed")
        read_only_fields = fields

    def get_profile_completed(self, obj) -> bool:
        # CandidateProfile arrives in Phase 3.1; until then nobody has one.
        return False


class RegisterSerializer(serializers.ModelSerializer):
    """04 §12.1. ``is_staff``/``is_superuser`` are never accepted (06 §4.4)."""

    # Explicit declaration: ModelSerializer would otherwise auto-attach
    # UniqueValidator to the unique model field, leaking "email exists" on
    # collisions — forbidden by D1/06 §2.4. Collision handling is the service's.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("email", "password", "password_confirm")

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        # Full pipeline (similarity vs email + complexity + common) against a
        # candidate user instance — the same validation reset-confirm reuses.
        validate_password(attrs["password"], user=User(email=attrs["email"]))
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(**validated_data)


class FamilyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login (04 §14): issues access+refresh with ``fam`` + ``is_verified`` claims."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token[api_settings.USER_ID_CLAIM] = str(user.id)  # force UUID, not str(pk) coercion drift
        token["fam"] = uuid4().hex  # token family id for reuse-detection
        token["is_verified"] = user.is_verified
        return token

    def validate(self, attrs):
        # 08 §6.2: a suspended account gets its own envelope (403 ACCOUNT_SUSPENDED),
        # but only AFTER the password proves the caller owns the account — a wrong
        # password on a banned account must still see the generic invalid-credentials
        # response (anti-enumeration). The lookup is indexed and hash-free for every
        # active user; check_password runs only on the inactive path.
        username_value = attrs.get(User.USERNAME_FIELD)
        candidate = None
        if username_value:
            candidate = User.objects.filter(**{User.USERNAME_FIELD: username_value}).first()
        if (
            candidate is not None
            and not candidate.is_active
            and candidate.check_password(attrs["password"])
        ):
            raise PermissionDenied(
                "This account has been suspended for violating community guidelines.",
                code="account_suspended",
            )
        data = super().validate(attrs)
        data["user"] = UserPrivateSerializer(self.user).data
        return data


class FamilyTokenRefreshSerializer(serializers.Serializer):
    """04 §15 rotation with family reuse-detection (AUTH-04 success criterion 3).

    SimpleJWT blacklists the submitted token at rotation but does NOT revoke
    its descendants; replaying a rotated token here blacklists the entire
    family (every outstanding token of the user sharing the same ``fam``).
    """

    refresh = serializers.CharField(write_only=True)
    access = serializers.CharField(read_only=True)

    def validate(self, attrs):
        raw = attrs["refresh"]
        try:
            refresh = RefreshToken(raw)
        except TokenError:
            # Malformed, expired, or already-replayed. For replays (signature
            # valid, jti blacklisted) revoke the whole family first.
            self._revoke_family_for_replay(raw)
            raise AuthenticationFailed("Token is invalid or expired.") from None

        user = self._user_from_payload(refresh.payload)
        # Hydrate the claim from the DB: the login-time value goes stale
        # the moment the user verifies mid-session.
        refresh["is_verified"] = user.is_verified if user else False

        # Rotation: blacklist submitted token, mint child jti/exp/iat and
        # record it as outstanding (so family members are enumerable).
        try:
            refresh.blacklist()
        except AttributeError:  # blacklist app missing — never in this project
            pass
        refresh.set_jti()
        refresh.set_exp()
        refresh.set_iat()
        refresh.outstand()

        return {"access": str(refresh.access_token), "refresh": str(refresh)}

    @staticmethod
    def _user_from_payload(payload):
        user_id = payload.get(api_settings.USER_ID_CLAIM)
        if not user_id:
            return None
        return User.objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first()

    def _revoke_family_for_replay(self, raw: str) -> None:
        try:
            payload = token_backend.decode(raw, verify=True)
        except Exception:
            return  # undecodable/expired — nothing to correlate; plain 401
        fam = payload.get("fam")
        user_id = payload.get(api_settings.USER_ID_CLAIM)
        if not fam or not user_id:
            return
        from apps.accounts.services import blacklist_token_family

        blacklist_token_family(user_id, fam)


class VerifyEmailSerializer(serializers.Serializer):
    """04 §13.2 Option A."""

    token = serializers.CharField(write_only=True)


class ResendVerificationSerializer(serializers.Serializer):
    """04 §13.1 request shape; response is always generic (06 §2.5)."""

    email = serializers.EmailField()


class PasswordResetRequestSerializer(serializers.Serializer):
    """04 §17.1 request shape; response is always generic (06 §3.5)."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """04 §17.2. Password pipeline runs in the service (needs the user)."""

    token = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    new_password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Passwords do not match."})
        return attrs


class LogoutSerializer(serializers.Serializer):
    """04 §16: submit the refresh token to blacklist."""

    refresh = serializers.CharField(write_only=True)


class DeleteAccountSerializer(serializers.Serializer):
    """04 §78: password re-authentication (T2.11)."""

    password = serializers.CharField(write_only=True, trim_whitespace=False)
