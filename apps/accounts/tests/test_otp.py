# apps/accounts/tests/test_otp.py
import pytest
from django.core.cache import cache
from django.core import mail
from django.conf import settings
from apps.accounts.services.otp import OTPService

@pytest.mark.django_db
class TestOTPService:
    """Test suite for OTPService."""
    
    class TestGenerateCode:
        """Tests for generate_code method."""
        
        def test_generate_code_returns_6_digits(self):
            """Should return a 6-digit string."""
            code = OTPService.generate_code()
            
            assert isinstance(code, str)
            assert len(code) == 6
            assert code.isdigit()
        
        def test_generate_code_range(self):
            """Should generate code between 100000 and 999999."""
            code = int(OTPService.generate_code())
            
            assert 100000 <= code <= 999999
        
        def test_generate_code_uniqueness(self):
            """Should generate different codes (probabilistic test)."""
            codes = {OTPService.generate_code() for _ in range(10)}
            
            # احتمال تکراری بودن بسیار کم است
            assert len(codes) >= 8
    
    class TestCreateOTP:
        """Tests for create_otp method."""
        
        def test_create_otp_returns_code(self, user):
            """Should create OTP and return code."""
            code = OTPService.create_otp(user.id, "password_reset")
            
            assert code is not None
            assert len(code) == 6
            assert code.isdigit()
        
        def test_create_otp_stores_in_cache(self, user):
            """Should store OTP data in cache."""
            user_id = user.id
            purpose = "password_reset"
            
            code = OTPService.create_otp(user_id, purpose)
            
            key = f"otp:{purpose}:{user_id}"
            data = cache.get(key)
            
            assert data is not None
            assert data["code"] == code
            assert data["attempts"] == 0
            assert "created_at" in data
            assert data["created_at"] is not None
        
        def test_create_otp_overwrites_existing(self, user):
            """Should overwrite existing OTP when creating new one."""
            user_id = user.id
            purpose = "password_reset"
            
            # Create first OTP
            code1 = OTPService.create_otp(user_id, purpose)
            key = f"otp:{purpose}:{user_id}"
            data1 = cache.get(key)
            
            # Create second OTP
            code2 = OTPService.create_otp(user_id, purpose)
            data2 = cache.get(key)
            
            assert code1 != code2
            assert data1["code"] != data2["code"]
            assert data2["attempts"] == 0
        
        def test_create_otp_default_purpose(self, user):
            """Should use default purpose if not specified."""
            code = OTPService.create_otp(user.id)
            
            key = f"otp:password_reset:{user.id}"
            data = cache.get(key)
            
            assert data is not None
            assert data["code"] == code
        
        def test_create_otp_custom_purpose(self, user):
            """Should use custom purpose if specified."""
            purpose = "login"
            code = OTPService.create_otp(user.id, purpose)
            
            key = f"otp:{purpose}:{user.id}"
            data = cache.get(key)
            
            assert data is not None
            assert data["code"] == code
    
    class TestVerifyOTP:
        """Tests for verify_otp method."""
        
        def test_verify_valid_otp(self, user):
            """Should verify valid OTP successfully."""
            user_id = user.id
            code = OTPService.create_otp(user_id, "password_reset")
            
            is_valid, error = OTPService.verify_otp(user_id, code, "password_reset")
            
            assert is_valid is True
            assert error is None
            # OTP should be deleted after successful verification
            key = f"otp:password_reset:{user_id}"
            assert cache.get(key) is None
        
        def test_verify_invalid_otp(self, user):
            """Should reject invalid OTP."""
            user_id = user.id
            OTPService.create_otp(user_id, "password_reset")
            
            is_valid, error = OTPService.verify_otp(user_id, "999999", "password_reset")
            
            assert is_valid is False
            assert "Invalid code" in error
            assert "2 attempts remaining" in error
        
        def test_verify_expired_otp(self, user, mocker):
            """Should reject expired OTP."""
            user_id = user.id
            OTPService.create_otp(user_id, "password_reset")
            
            # Simulate cache expiration
            mocker.patch("django.core.cache.cache.get", return_value=None)
            
            is_valid, error = OTPService.verify_otp(user_id, "123456", "password_reset")
            
            assert is_valid is False
            assert "expired" in error.lower()
        
        def test_verify_max_attempts(self, user):
            """Should block after max failed attempts."""
            user_id = user.id
            OTPService.create_otp(user_id, "password_reset")
            
            # Try 3 times with wrong code
            for i in range(OTPService.MAX_ATTEMPTS):
                is_valid, error = OTPService.verify_otp(
                    user_id, "999999", "password_reset"
                )
                assert is_valid is False
            
            # Fourth attempt should fail with max attempts message
            is_valid, error = OTPService.verify_otp(
                user_id, "999999", "password_reset"
            )
            
            assert is_valid is False
            assert "Too many failed attempts" in error
        
        def test_verify_attempts_count_increases(self, user):
            """Should increment attempts counter on failed verification."""
            user_id = user.id
            OTPService.create_otp(user_id, "password_reset")
            key = f"otp:password_reset:{user_id}"
            
            # First failed attempt
            OTPService.verify_otp(user_id, "999999", "password_reset")
            data = cache.get(key)
            assert data["attempts"] == 1
            
            # Second failed attempt
            OTPService.verify_otp(user_id, "999998", "password_reset")
            data = cache.get(key)
            assert data["attempts"] == 2
        
        def test_verify_deletes_otp_after_max_attempts(self, user):
            """Should delete OTP after max attempts exceeded."""
            user_id = user.id
            OTPService.create_otp(user_id, "password_reset")
            key = f"otp:password_reset:{user_id}"
            
            # Exceed max attempts
            for _ in range(OTPService.MAX_ATTEMPTS + 1):
                OTPService.verify_otp(user_id, "999999", "password_reset")
            
            # OTP should be deleted
            assert cache.get(key) is None
        
        def test_verify_wrong_purpose(self, user):
            """Should not verify OTP for different purpose."""
            user_id = user.id
            OTPService.create_otp(user_id, "password_reset")
            
            is_valid, error = OTPService.verify_otp(
                user_id, "123456", "login"
            )
            
            assert is_valid is False
            assert "expired" in error.lower()
    
    class TestSendOTPEmail:
        """Tests for send_otp_email method."""
        
        def test_send_otp_email_success(self, user, mock_send_mail):
            """Should send OTP email successfully."""
            code = "123456"
            
            success, error = OTPService.send_otp_email(user, code)
            
            assert success is True
            assert error is None
            mock_send_mail.assert_called_once_with(
                subject="Password Reset OTP Code",
                message=f"Your OTP code is: {code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        
        def test_send_otp_email_with_exception(self, user, mock_send_mail, mock_logger):
            """Should handle exception when sending email fails."""
            code = "123456"
            mock_send_mail.side_effect = Exception("SMTP connection failed")
            
            success, error = OTPService.send_otp_email(user, code)
            
            assert success is False
            assert "Failed to send OTP email" in error
            mock_logger.assert_called_once()
            # Check that logger was called with the right message
            call_args = mock_logger.call_args[0][0]
            assert "Failed to send OTP email" in call_args
            assert "SMTP connection failed" in call_args
        
        def test_send_otp_email_uses_correct_email(self, user, mock_send_mail):
            """Should send email to user's email address."""
            code = "123456"
            
            OTPService.send_otp_email(user, code)
            
            call_args = mock_send_mail.call_args[1]
            assert call_args["recipient_list"] == [user.email]
        
        def test_send_otp_email_fail_silently_true(self, user, mock_send_mail):
            """Should use fail_silently=True."""
            code = "123456"
            
            OTPService.send_otp_email(user, code)
            
            call_args = mock_send_mail.call_args[1]
            assert call_args["fail_silently"] is True
    
    class TestSendOTPSMS:
        """Tests for send_otp_sms method."""
        
        def test_send_otp_sms_placeholder(self):
            """Should be implemented later."""
            # This is just a placeholder test
            # When you implement SMS, add proper tests
            pass
    
    class TestIntegration:
        """Integration tests for complete flow."""
        
        def test_full_otp_flow_success(self, user):
            """Should complete full OTP flow successfully."""
            # Step 1: Create OTP
            code = OTPService.create_otp(user.id, "password_reset")
            
            # Step 2: Send email
            success, error = OTPService.send_otp_email(user, code)
            assert success is True
            
            # Step 3: Verify OTP
            is_valid, error = OTPService.verify_otp(user.id, code, "password_reset")
            assert is_valid is True
            assert error is None
        
        def test_full_otp_flow_with_wrong_code(self, user):
            """Should handle wrong code in full flow."""
            # Create OTP
            code = OTPService.create_otp(user.id, "password_reset")
            
            # Try with wrong code
            is_valid, error = OTPService.verify_otp(
                user.id, "999999", "password_reset"
            )
            assert is_valid is False
            assert "Invalid code" in error
            
            # Original code should still work
            is_valid, error = OTPService.verify_otp(user.id, code, "password_reset")
            assert is_valid is True
        
        def test_multiple_users_independent(self, user):
            """Should handle OTP for multiple users independently."""
            # Create another user
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user2 = User.objects.create_user(
                username="testuser2",
                email="test2@example.com",
                password="testpass123"
            )
            
            # Create OTPs for both users
            code1 = OTPService.create_otp(user.id, "password_reset")
            code2 = OTPService.create_otp(user2.id, "password_reset")
            
            # Verify OTP for user1
            is_valid, error = OTPService.verify_otp(user.id, code1, "password_reset")
            assert is_valid is True
            
            # User2's OTP should still work
            is_valid, error = OTPService.verify_otp(user2.id, code2, "password_reset")
            assert is_valid is True