# apps/accounts/services/otp.py

import secrets
import hmac
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
import logging

class OTPService:
    """Simple OTP service using cache with secure comparison."""
    
    OTP_EXPIRE_SECONDS = 600  
    MAX_ATTEMPTS = 3
    
    @staticmethod
    def _get_key(user_id, purpose="password_reset"):
        """Generate cache key for OTP."""
        return f"otp:{purpose}:{user_id}"
    
    @staticmethod
    def generate_code():
        """Generate 6-digit OTP code."""
        return f"{secrets.randbelow(900000) + 100000}"
    
    @staticmethod
    def _secure_compare(a, b):
        """
        مقایسه امن دو رشته با استفاده از hmac.compare_digest
        مقاوم در برابر Timing Attack
        """
        return hmac.compare_digest(a, b)
    
    @staticmethod
    def create_otp(user_id, purpose="password_reset"):
        """
        Create and store OTP in cache.
        Returns the OTP code.
        """
        key = OTPService._get_key(user_id, purpose)
        
        cache.delete(key)
        
        code = OTPService.generate_code()
        
        data = {
            "code_hash": OTPService._hash_code(code),  
            "attempts": 0,
            "created_at": timezone.now().isoformat(),
        }
        
        cache.set(key, data, timeout=OTPService.OTP_EXPIRE_SECONDS)
        return code
    
    @staticmethod
    def _hash_code(code):
        """هش کردن OTP برای امنیت بیشتر (اختیاری)"""
        import hashlib
        return hashlib.sha256(code.encode()).hexdigest()
    
    @staticmethod
    def verify_otp(user_id, code, purpose="password_reset"):
        """
        Verify OTP code securely.
        Returns (is_valid, error_message).
        """
        key = OTPService._get_key(user_id, purpose)
        data = cache.get(key)
        
        if not data:
            return False, "OTP code has expired. Please request a new one."
        
        if data["attempts"] >= OTPService.MAX_ATTEMPTS:
            cache.delete(key)      
            return False, "Too many failed attempts. Please request a new OTP."
        
        # ✅ استفاده از مقایسه امن
        stored_code = data.get("code")
        stored_hash = data.get("code_hash")
        
        # اگر کد به صورت hash ذخیره شده
        if stored_hash:
            provided_hash = OTPService._hash_code(code)
            is_valid = OTPService._secure_compare(provided_hash, stored_hash)
        else:
            # fallback برای کدهای قدیمی
            is_valid = OTPService._secure_compare(code, stored_code)
        
        if not is_valid:
            data["attempts"] += 1
            remaining = OTPService.MAX_ATTEMPTS - data["attempts"]
            cache.set(key, data, timeout=OTPService.OTP_EXPIRE_SECONDS)
            
            if remaining == 0:
                return False, "Too many failed attempts. Please request a new OTP."
            return False, f"Invalid code. {remaining} attempts remaining."
        
        cache.delete(key)
        return True, None
    
    @staticmethod
    def send_otp_email(user, code):
        """Send OTP code via email."""
        try:
            send_mail(
                subject="Password Reset OTP Code",
                message=f"Your OTP code is: {code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,  
            )
            return True, None
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
            return False, "Failed to send OTP email. Please try again."
        
    @staticmethod
    def send_otp_sms(phone_number, code):
        """Send OTP via SMS."""
        # پیاده‌سازی با سرویس SMS
        pass