from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.api.v1.serializers.authentication import (
    ChangePasswordSerializer,
    DeviceSessionRefreshSerializer,
    DeviceSessionSerializer,
    LoginSerializer,
    PasswordResetOTPSerializer,
    PasswordResetRequestOTPSerializer,
    RegisterSerializer,
)
from apps.accounts.models import DeviceSession
from apps.accounts.services.authentication import (
    create_device_session,
    revoke_all_device_sessions,
    revoke_device_session,
)


class RegisterView(APIView):
    """
    Register a new user account.
    
    Creates a new user with the provided credentials. After successful
    registration, the user is NOT automatically logged in - they must
    call the login endpoint separately.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.save()
        
        return Response(
            {
                "message": "Registration successful. Please log in.",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            },
            status=status.HTTP_201_CREATED,
        )

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        result = create_device_session(
            user=serializer.validated_data["user"],
            device_name=serializer.validated_data.get("device_name", ""),
            device_type=serializer.validated_data.get("device_type", ""),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

        return Response(
            {
                "message": "Login successful.",
                "tokens": {
                    "access": result["access"],
                    "refresh": result["refresh"],
                },
                "session": DeviceSessionSerializer(result["session"]).data,
            },
            status=status.HTTP_200_OK,
        )


class RefreshTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DeviceSessionRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        session_id = request.auth.get("sid")
        session = DeviceSession.objects.filter(
            id=session_id,
            user=request.user,
            revoked_at__isnull=True,
        ).first()

        if session is not None:
            revoke_device_session(session=session)

        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class LogoutAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        count = revoke_all_device_sessions(user=request.user)
        return Response(
            {"message": "All device sessions have been revoked.", "revoked_sessions": count},
            status=status.HTTP_200_OK,
        )


class DeviceSessionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sessions = DeviceSession.objects.filter(
            user=request.user,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        return Response(DeviceSessionSerializer(sessions, many=True).data)


class DeviceSessionRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, session_id):
        session = DeviceSession.objects.filter(
            id=session_id,
            user=request.user,
            revoked_at__isnull=True,
        ).first()

        if session is None:
            return Response(
                {"message": "Device session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        revoke_device_session(session=session)
        return Response(status=status.HTTP_204_NO_CONTENT)



class PasswordResetRequestOTPView(APIView):
    """Request OTP code."""
    
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"
    
    def post(self, request):
        serializer = PasswordResetRequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.context["user"]
        
        # تولید OTP
        from apps.accounts.services.otp import OTPService
        code = OTPService.create_otp(user.id, purpose="password_reset")
        
        # ارسال ایمیل
        OTPService.send_otp_email(user.email, code)
        
        return Response({
            "message": "OTP code sent to your email.",
            "expires_in_minutes": 10,
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmOTPView(APIView):
    """Reset password using OTP."""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = PasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({
            "message": "Password reset successfully.",
        }, status=status.HTTP_200_OK)
   
            
class ChangePasswordView(APIView):
    """
    Change password for authenticated user.
    
    Requires current password for verification. After successful change,
    revokes all other sessions to force re-login everywhere except current device.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        session_id = request.auth.get("sid") if request.auth else None
        revoke_all_device_sessions(
            user=request.user,
            except_session_id=session_id,
            
        )
        
        return Response(
            {
                "message": "Password changed successfully. All other devices have been logged out.",
            },
            status=status.HTTP_200_OK,
        )