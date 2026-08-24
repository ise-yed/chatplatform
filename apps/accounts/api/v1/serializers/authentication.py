from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.utils import datetime_from_epoch

from apps.accounts.models import DeviceSession, User


class RegisterSerializer(serializers.ModelSerializer):
    """Validate registration data and create a new user."""
    
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
        error_messages={
            "min_length": "Password must be at least 8 characters long.",
        }
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    email = serializers.EmailField(required=True)
    
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
        )
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
        }
    
    def validate_username(self, value):
        """Ensure username is unique and valid."""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value
    
    def validate_email(self, value):
        """Ensure email is unique and valid."""
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate(self, attrs):
        """Check that passwords match."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs
    
    def create(self, validated_data):
        """Create and return the user."""
        validated_data.pop("password_confirm")
        
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        
        return user

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
            "auth_type",
            "device_name",
            "device_type",
            "last_used_at",
            "created_at",
            "expires_at",
            "is_active",
        )
        read_only_fields = fields

    def get_is_active(self, obj):
        return obj.is_active


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
