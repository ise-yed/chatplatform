from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.utils import datetime_from_epoch

from apps.accounts.models import DeviceSession, User


class LoginSerializer(serializers.Serializer):
    """Validate user credentials and collect client device metadata."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    device_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    device_type = serializers.CharField(required=False, allow_blank=True, max_length=30)

    def validate(self, attrs):
        username = attrs["username"].strip()
        password = attrs["password"]

        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=password,
        )

        if user is None:
            raise serializers.ValidationError("Invalid username or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")

        attrs["user"] = user
        return attrs


class DeviceSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = DeviceSession
        fields = (
            "id",
            "device_name",
            "device_type",
            "last_used_at",
            "created_at",
            "expires_at",
            "is_active",
        )
        read_only_fields = fields

    def get_is_active(self, obj):
        return obj.revoked_at is None and (
            obj.expires_at is None or obj.expires_at > timezone.now()
        )


class DeviceSessionRefreshSerializer(TokenRefreshSerializer):
    """Refresh JWTs only while their DeviceSession is still active."""

    @transaction.atomic
    def validate(self, attrs):
        raw_refresh = attrs["refresh"]

        try:
            refresh = RefreshToken(raw_refresh)
            session_id = refresh["sid"]
            user_id = refresh["user_id"]
        except (TokenError, KeyError):
            raise serializers.ValidationError({"refresh": "Invalid refresh token."})

        session = (
            DeviceSession.objects.select_for_update()
            .filter(
                id=session_id,
                user_id=user_id,
                revoked_at__isnull=True,
            )
            .first()
        )

        if session is None:
            raise serializers.ValidationError({"refresh": "Device session is revoked or invalid."})

        if session.expires_at is not None and session.expires_at <= timezone.now():
            raise serializers.ValidationError({"refresh": "Device session has expired."})

        data = super().validate(attrs)

        update_fields = ["last_used_at", "updated_at"]
        session.last_used_at = timezone.now()

        rotated_refresh = data.get("refresh")
        if rotated_refresh:
            new_refresh = RefreshToken(rotated_refresh)
            session.refresh_token_jti = new_refresh["jti"]
            session.expires_at = datetime_from_epoch(new_refresh["exp"])
            update_fields.extend(["refresh_token_jti", "expires_at"])

        session.save(update_fields=update_fields)

        return data
