# apps/accounts/services/otp.py

from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
import random
import secrets

from django.utils import timezone


class OTPService:
    """Simple OTP service using cache."""
    
    OTP_EXPIRE_SECONDS = 600  # 10 دقیقه
    MAX_ATTEMPTS = 3
    
    @staticmethod
    def _get_key(user_id, purpose="password_reset"):
        """Generate cache key for OTP."""
        return f"otp:{purpose}:{user_id}"
    
    @staticmethod
    def generate_code():
        """Generate 6-digit OTP code."""
        return f"{random.randint(100000, 999999)}"
    
    @staticmethod
    def create_otp(user_id, purpose="password_reset"):
        """
        Create and store OTP in cache.
        Returns the OTP code.
        """
        key = OTPService._get_key(user_id, purpose)
        
        # حذف OTP قبلی
        cache.delete(key)
        
        # تولید کد جدید
        code = OTPService.generate_code()
        
        # ذخیره در کش با اطلاعات اضافی
        data = {
            "code": code,
            "attempts": 0,
            "created_at": timezone.now().isoformat(),
        }
        
        cache.set(key, data, timeout=OTPService.OTP_EXPIRE_SECONDS)
        return code
    
    @staticmethod
    def verify_otp(user_id, code, purpose="password_reset"):
        """
        Verify OTP code.
        Returns (is_valid, error_message).
        """
        key = OTPService._get_key(user_id, purpose)
        data = cache.get(key)
        
        if not data:
            return False, "OTP code has expired. Please request a new one."
        
        # بررسی تعداد تلاش‌ها
        if data["attempts"] >= OTPService.MAX_ATTEMPTS:
            cache.delete(key)  # قفل شدن
            return False, "Too many failed attempts. Please request a new OTP."
        
        # بررسی کد
        if data["code"] != code:
            data["attempts"] += 1
            remaining = OTPService.MAX_ATTEMPTS - data["attempts"]
            cache.set(key, data, timeout=OTPService.OTP_EXPIRE_SECONDS)
            
            if remaining == 0:
                return False, "Too many failed attempts. Please request a new OTP."
            return False, f"Invalid code. {remaining} attempts remaining."
        
        # موفقیت - حذف OTP
        cache.delete(key)
        return True, None
    
    @staticmethod
    def send_otp_email(email, code):
        """Send OTP via email."""
        subject = "Your OTP Code"
        message = f"Your OTP code is: {code}\n\nThis code expires in 10 minutes."
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    
    @staticmethod
    def send_otp_sms(phone_number, code):
        """Send OTP via SMS."""
        # پیاده‌سازی با سرویس SMS
        pass