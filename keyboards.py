from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import SHOP_PRICES

def main_keyboard():
    """Main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 حسابي", callback_data="account"),
         InlineKeyboardButton("🎁 هديتي اليومية", callback_data="daily_reward")],
        [InlineKeyboardButton("🧑‍🤝‍🧑 دعوة أصدقاء", callback_data="referral"),
         InlineKeyboardButton("📢 تجميع قنوات", callback_data="channels")],
        [InlineKeyboardButton("⭐ قنوات VIP", callback_data="vip_channels"),
         InlineKeyboardButton("🛒 المتجر", callback_data="shop")],
        [InlineKeyboardButton("🎟️ استخدام كود", callback_data="redeem_code")]
    ]
    return InlineKeyboardMarkup(keyboard)

def shop_keyboard():
    """Shop menu keyboard"""
    keyboard = []
    for members, points in SHOP_PRICES.items():
        keyboard.append([InlineKeyboardButton(
            f"{members} أعضاء - {points} نقطة", 
            callback_data=f"buy_{members}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def channels_keyboard(channels, user_subscriptions=None):
    """Normal channels list keyboard with status indicators"""
    keyboard = []
    user_subscriptions = user_subscriptions or []
    
    for channel in channels:
        points = 3  # Normal channels = 3 points
        status_icon = "✅" if channel['username'] in user_subscriptions else "📢"
        progress = f"{channel['gained']}/{channel['target']}"
        
        keyboard.append([InlineKeyboardButton(
            f"{status_icon} @{channel['username']} ({progress}) - {points} نقاط",
            callback_data=f"join_{channel['username']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔄 تحديث", callback_data="refresh_channels")])
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def vip_channels_keyboard(channels, user_subscriptions=None):
    """VIP channels list keyboard with status indicators"""
    keyboard = []
    user_subscriptions = user_subscriptions or []
    
    for channel in channels:
        points = 4  # VIP channels = 4 points
        status_icon = "✅" if channel['username'] in user_subscriptions else "⭐"
        progress = f"{channel['gained']}/{channel['target']}"
        
        keyboard.append([InlineKeyboardButton(
            f"{status_icon} @{channel['username']} ({progress}) - {points} نقاط",
            callback_data=f"join_{channel['username']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔄 تحديث", callback_data="refresh_vip_channels")])
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_main")])
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    """Admin menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users"),
         InlineKeyboardButton("📢 إدارة القنوات", callback_data="admin_channels")],
        [InlineKeyboardButton("📦 الطلبات", callback_data="admin_orders"),
         InlineKeyboardButton("🎟️ إدارة الأكواد", callback_data="admin_codes")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats"),
         InlineKeyboardButton("📣 بث رسالة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔍 معلومات المستخدم", callback_data="admin_user_info"),
         InlineKeyboardButton("🔒 قنوات إجبارية", callback_data="admin_mandatory_channels")],
        [InlineKeyboardButton("➕ إضافة قناة عادية", callback_data="admin_add_normal_channel"),
         InlineKeyboardButton("⭐ إضافة قناة VIP", callback_data="admin_add_vip_channel")],
        [InlineKeyboardButton("➖ حذف قناة", callback_data="admin_remove_channel"),
         InlineKeyboardButton("💰 إضافة نقاط", callback_data="admin_add_points")],
        [InlineKeyboardButton("🚫 خصم نقاط", callback_data="admin_remove_points"),
         InlineKeyboardButton("🔨 حظر مستخدم", callback_data="admin_ban_user")],
        [InlineKeyboardButton("✅ إلغاء حظر", callback_data="admin_unban_user"),
         InlineKeyboardButton("➕ إضافة قناة إجبارية", callback_data="admin_add_mandatory")],
        [InlineKeyboardButton("➖ حذف قناة إجبارية", callback_data="admin_remove_mandatory")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    """Simple back button"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="back_to_main")]])

def admin_back_keyboard():
    """Back to admin menu"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="admin_menu")]])

def confirmation_keyboard(action, data):
    """Confirmation keyboard for actions"""
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد", callback_data=f"confirm_{action}_{data}"),
         InlineKeyboardButton("❌ إلغاء", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)
