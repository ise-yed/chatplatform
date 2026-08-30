from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.v1.serializers import (
    UserProfileUpdateSerializer,
)
from apps.accounts.services.profile import update_user_profile


class UserProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)

        user = update_user_profile(
            user=request.user,
            validated_data=serializer.validated_data,
        )

        return Response(
            UserProfileUpdateSerializer(user).data,
            status=status.HTTP_200_OK,
        )