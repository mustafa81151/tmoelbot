import logging
import re
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )

def extract_user_id_from_start(text: str) -> Optional[int]:
    """Extract referrer user ID from /start command"""
    if not text.startswith('/start'):
        return None
    
    parts = text.split()
    if len(parts) > 1:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None

def is_valid_channel_username(username: str) -> bool:
    """Validate channel username format"""
    if not username:
        return False
    
    # Remove @ if present
    username = username.replace('@', '')
    
    # Check format: 5-32 characters, letters, digits, underscores
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$'
    return bool(re.match(pattern, username))

def format_number(number: int) -> str:
    """Format number with Arabic thousand separators"""
    return f"{number:,}".replace(',', '٬')

def validate_points_amount(amount_str: str) -> Optional[int]:
    """Validate and convert points amount string to integer"""
    try:
        amount = int(amount_str)
        if amount <= 0:
            return None
        return amount
    except ValueError:
        return None

async def check_user_membership(bot: Bot, user_id: int, channel_username: str) -> bool:
    """Check if user is a real member of the channel (not fake/bot account)"""
    try:
        member = await bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user_id)
        
        # Check if user is actually a member
        if member.status not in ['member', 'administrator', 'creator']:
            return False
            
        # Additional verification: Check if user account appears legitimate
        user = member.user
        
        # Basic checks for fake accounts
        if user.is_bot:
            logging.warning(f"Bot account detected trying to join @{channel_username}: {user_id}")
            return False
            
        # Advanced verification for fake accounts
        is_suspicious = False
        warnings = []
        
        # Check for suspicious username patterns
        if user.username:
            if len(user.username) < 5:
                warnings.append("username too short")
                is_suspicious = True
            # Check for bot-like patterns (numbers only, random chars)
            if user.username.isdigit():
                warnings.append("username is all numbers")
                is_suspicious = True
        else:
            warnings.append("no username")
            
        # Check if user has first name (fake accounts often don't)
        if not user.first_name or len(user.first_name.strip()) < 2:
            warnings.append("no proper first name")
            is_suspicious = True
            
        # Check for recently created accounts (if possible through user ID patterns)
        if user_id > 6000000000:  # Recently created accounts tend to have high IDs
            warnings.append("potentially new account")
            
        # Log verification results
        if is_suspicious:
            logging.warning(f"⚠️ Suspicious account @{user.username or 'no_username'} ({user_id}) in @{channel_username}: {', '.join(warnings)}")
        else:
            logging.info(f"✅ Verified legitimate user {user_id} (@{user.username or 'no_username'}) in @{channel_username}")
            
        # Allow user but log concerns (you can make this stricter if needed)
        return True
        
    except TelegramError as e:
        logging.error(f"Error checking membership for @{channel_username}: {e}")
        return False

async def get_channel_member_count(bot: Bot, channel_username: str) -> int:
    """Get the current member count of a channel"""
    try:
        chat = await bot.get_chat(chat_id=f"@{channel_username}")
        # Handle different API response formats
        if hasattr(chat, 'member_count'):
            return chat.member_count or 0
        elif hasattr(chat, 'members_count'):
            return chat.members_count or 0
        else:
            # Fallback: try to get chat administrators count as approximation
            return 1
    except TelegramError as e:
        logging.error(f"Error getting member count for @{channel_username}: {e}")
        return 0

def parse_admin_command(text: str) -> tuple:
    """Parse admin command and return command parts"""
    parts = text.split()
    if len(parts) < 2:
        return None, []
    
    command = parts[0]
    args = parts[1:]
    return command, args

def generate_referral_link(bot_username: str, user_id: int) -> str:
    """Generate referral link for user"""
    return f"https://t.me/{bot_username}?start={user_id}"

async def check_channel_membership_simple(bot, user_id: int, channel_username: str) -> bool:
    """Simple check if user is a member of the channel - Works without admin permissions"""
    try:
        member = await bot.get_chat_member(f"@{channel_username}", user_id)
        # Check if user is a member (not kicked, left, or restricted)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f"Error checking membership for @{channel_username}: {e}")
        # If we can't check, assume they're not a member
        return False

async def check_mandatory_channels_membership(bot, user_id: int, mandatory_channels: list) -> tuple:
    """Check membership in mandatory channels and return missing ones"""
    missing_channels = []
    
    for channel in mandatory_channels:
        is_member = await check_channel_membership_simple(bot, user_id, channel['channel_username'])
        if not is_member:
            missing_channels.append(channel)
    
    return len(missing_channels) == 0, missing_channels

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

class MessageTemplates:
    """Pre-formatted message templates"""
    
    @staticmethod
    def user_stats(user_data: dict) -> str:
        """Format user statistics message"""
        return (
            f"📊 معلومات حسابك:\n\n"
            f"💰 النقاط: {format_number(user_data['points'])}\n"
            f"👥 الإحالات: {format_number(user_data['referrals'])}\n"
            f"📢 القنوات المنضم إليها: {format_number(user_data['channels_joined'])}\n"
            f"📅 تاريخ التسجيل: {user_data['created_at'][:10]}"
        )
    
    @staticmethod
    def order_confirmation(channel_username: str, members: int, points: int) -> str:
        """Format order confirmation message"""
        return (
            f"✅ تم إنشاء طلبك بنجاح!\n\n"
            f"📢 القناة: @{channel_username}\n"
            f"👥 الأعضاء المطلوبين: {format_number(members)}\n"
            f"💰 النقاط المخصومة: {format_number(points)}\n\n"
            f"سيتم إضافة قناتك إلى قائمة التجميع وإزالتها تلقائياً عند اكتمال العدد المطلوب."
        )
    
    @staticmethod
    def admin_stats(stats: dict) -> str:
        """Format admin statistics message"""
        return (
            f"📊 إحصائيات البوت:\n\n"
            f"👥 إجمالي المستخدمين: {format_number(stats['users'])}\n"
            f"📢 القنوات النشطة: {format_number(stats['channels'])}\n"
            f"💰 إجمالي النقاط الموزعة: {format_number(stats['total_points'])}\n"
            f"📦 الطلبات النشطة: {format_number(stats['active_orders'])}"
        )
    
    @staticmethod
    def order_list(orders: list) -> str:
        """Format orders list for admin"""
        if not orders:
            return "📦 لا توجد طلبات حالياً"
        
        message = "📦 قائمة الطلبات:\n\n"
        for order in orders[:10]:  # Show only first 10
            status_emoji = "🟢" if order['status'] == 'active' else "✅" if order['status'] == 'completed' else "❌"
            user_name = order.get('username', 'غير معروف')
            message += (
                f"{status_emoji} @{order['channel_username']}\n"
                f"👤 {user_name} ({order['user_id']})\n"
                f"👥 {order['members_count']} عضو\n"
                f"📅 {order['created_at'][:16]}\n\n"
            )
        
        if len(orders) > 10:
            message += f"... و {len(orders) - 10} طلب آخر"
        
        return message
