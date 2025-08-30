import asyncio
from telegram import Bot, User
from telegram.error import TelegramError
import logging

async def check_user_legitimacy(bot: Bot, user: User) -> dict:
    """
    Check if user appears to be legitimate or fake
    Returns dict with is_legitimate bool and warnings list
    """
    warnings = []
    is_legitimate = True
    
    try:
        # Check if user has a profile photo
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count == 0:
            warnings.append("لا يوجد صورة شخصية")
            is_legitimate = False
        
        # Check if first name exists and is reasonable
        if not user.first_name or len(user.first_name.strip()) < 2:
            warnings.append("اسم غير مناسب")
            is_legitimate = False
        
        # Check for suspicious patterns in name
        suspicious_patterns = ['test', 'bot', '123', 'fake', 'spam']
        name_lower = user.first_name.lower() if user.first_name else ""
        if any(pattern in name_lower for pattern in suspicious_patterns):
            warnings.append("اسم مشبوه")
            is_legitimate = False
        
        # Check if username exists (optional but good sign)
        if not user.username:
            warnings.append("لا يوجد معرف")
            # Don't mark as illegitimate just for missing username
        
        # Check user ID patterns (very new accounts might be suspicious)
        if user.id > 6000000000:  # Very high ID numbers might indicate recent bot creation
            warnings.append("حساب جديد جداً")
        
    except TelegramError as e:
        logging.error(f"Error checking user legitimacy: {e}")
        warnings.append("خطأ في التحقق")
        is_legitimate = False
    
    return {
        'is_legitimate': is_legitimate,
        'warnings': warnings
    }