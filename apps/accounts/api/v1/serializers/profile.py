from rest_framework import serializers

from apps.accounts.models import User


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "avatar",
        )
        extra_kwargs = {
            "username": {
                "required": False,
                "allow_blank": False,
                "max_length": 150,
            },
            "email": {
                "required": False,
                "allow_blank": False,
            },
            "avatar": {
                "required": False,
                "allow_null": True,
            },
        }

    def validate_username(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Username cannot be empty."
            )

        if (
            User.objects
            .filter(username__iexact=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "This username is already taken."
            )

        return value

    def validate_email(self, value):
        value = value.strip().lower()

        if (
            User.objects
            .filter(email__iexact=value)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                "This email is already in use."
            )

        return value