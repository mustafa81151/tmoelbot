import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from database import Database
from keyboards import admin_keyboard, admin_back_keyboard
from config import ADMIN_ID, ADMIN_MESSAGES
from utils import parse_admin_command, is_valid_channel_username, MessageTemplates

class AdminHandlers:
    def __init__(self, database: Database):
        self.db = database
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == ADMIN_ID
    
    async def admin_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin menu"""
        if not self.is_admin(update.effective_user.id):
            return
        
        message = "👑 لوحة التحكم الإدارية\n\nاختر العملية المطلوبة:"
        
        if update.message:
            await update.message.reply_text(message, reply_markup=admin_keyboard())
        else:
            await update.callback_query.edit_message_text(message, reply_markup=admin_keyboard())
    
    async def add_points(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add points to user - Command: /addpoints @username/user_id points"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/addpoints @username points\nأو\n/addpoints user_id points\n\nمثال: /addpoints @user123 100"
            )
            return
        
        user_identifier = args[0]
        try:
            points = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ يجب أن تكون النقاط رقم صحيح")
            return
        
        # Check if it's username or user_id
        if user_identifier.startswith('@'):
            user_data = self.db.get_user_by_username(user_identifier)
            if user_data:
                user_id = user_data['id']
                display_name = f"@{user_data['username']}"
            else:
                await update.message.reply_text(f"❌ المستخدم {user_identifier} غير موجود")
                return
        else:
            try:
                user_id = int(user_identifier)
                user_data = self.db.get_user(user_id)
                if user_data:
                    display_name = f"@{user_data['username']}" if user_data.get('username') else str(user_id)
                else:
                    await update.message.reply_text(f"❌ المستخدم {user_identifier} غير موجود")
                    return
            except ValueError:
                await update.message.reply_text("❌ يجب استخدام @username أو رقم المستخدم")
                return
        
        if self.db.update_user_points(user_id, points):
            message = f"✅ تم إضافة {points} نقطة للمستخدم {display_name}"
        else:
            message = "❌ حدث خطأ في إضافة النقاط"
        
        await update.message.reply_text(message)
    
    async def remove_points(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove points from user - Command: /removepoints @username/user_id points"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/removepoints @username points\nأو\n/removepoints user_id points\n\nمثال: /removepoints @user123 50"
            )
            return
        
        user_identifier = args[0]
        try:
            points = int(args[1])
        except ValueError:
            await update.message.reply_text("❌ يجب أن تكون النقاط رقم صحيح")
            return
        
        # Check if it's username or user_id
        if user_identifier.startswith('@'):
            user_data = self.db.get_user_by_username(user_identifier)
            if user_data:
                user_id = user_data['id']
                display_name = f"@{user_data['username']}"
            else:
                await update.message.reply_text(f"❌ المستخدم {user_identifier} غير موجود")
                return
        else:
            try:
                user_id = int(user_identifier)
                user_data = self.db.get_user(user_id)
                if user_data:
                    display_name = f"@{user_data['username']}" if user_data.get('username') else str(user_id)
                else:
                    await update.message.reply_text(f"❌ المستخدم {user_identifier} غير موجود")
                    return
            except ValueError:
                await update.message.reply_text("❌ يجب استخدام @username أو رقم المستخدم")
                return
        
        if self.db.update_user_points(user_id, -points):
            message = f"✅ تم خصم {points} نقطة من المستخدم {display_name}"
        else:
            message = "❌ حدث خطأ في خصم النقاط"
        
        await update.message.reply_text(message)
    
    async def add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add channel - Command: /addchannel @channel type target"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if len(args) != 3:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/addchannel @channel type target\n\n"
                "الأنواع المتاحة: normal, vip\n"
                "مثال: /addchannel @mychannel vip 1000"
            )
            return
        
        channel_username = args[0].replace('@', '')
        channel_type = args[1].lower()
        
        if channel_type not in ['normal', 'vip']:
            await update.message.reply_text("❌ النوع يجب أن يكون: normal أو vip")
            return
        
        try:
            target = int(args[2])
        except ValueError:
            await update.message.reply_text("❌ الهدف يجب أن يكون رقم صحيح")
            return
        
        if not is_valid_channel_username(channel_username):
            await update.message.reply_text("❌ اسم القناة غير صحيح")
            return
        
        # Admin commands are free - no payment required
        price = 0  # Free for admin
        
        # Create order first (free for admin)
        order_id = self.db.create_order(update.effective_user.id, channel_username, price, target)
        
        if order_id and self.db.add_channel(channel_username, channel_type, target, order_id):
            message = f"✅ تم تفعيل القناة @{channel_username}\n📊 النوع: {channel_type}\n🎯 الهدف: {target} عضو\n💰 السعر: {price} نقطة\n🆔 رقم الطلب: {order_id}"
        else:
            message = "❌ حدث خطأ في إضافة القناة"
        
        await update.message.reply_text(message)
    
    async def remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove channel - Command: /removechannel @channel"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if len(args) != 1:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/removechannel @channel\n\nمثال: /removechannel @mychannel"
            )
            return
        
        channel_username = args[0].replace('@', '')
        
        if self.db.remove_channel(channel_username):
            message = ADMIN_MESSAGES['channel_removed'].format(channel=channel_username)
        else:
            message = "❌ القناة غير موجودة"
        
        await update.message.reply_text(message)
    
    async def make_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create redemption code - Command: /makecode code points limit"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if len(args) != 3:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/makecode code points limit\n\n"
                "مثال: /makecode GIFT100 100 50"
            )
            return
        
        code = args[0]
        
        try:
            points = int(args[1])
            limit = int(args[2])
        except ValueError:
            await update.message.reply_text("❌ النقاط والحد الأقصى يجب أن يكونا أرقام صحيحة")
            return
        
        if self.db.create_code(code, points, limit):
            message = ADMIN_MESSAGES['code_created'].format(code=code, points=points, limit=limit)
        else:
            message = "❌ الكود موجود مسبقاً"
        
        await update.message.reply_text(message)
    
    async def view_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View orders - Command: /orders [status]"""
        if not self.is_admin(update.effective_user.id):
            return
        
        status = context.args[0] if context.args else None
        orders = self.db.get_orders(status=status)
        
        message = MessageTemplates.order_list(orders)
        await update.message.reply_text(message)
    
    async def view_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View bot statistics - Command: /stats"""
        if not self.is_admin(update.effective_user.id):
            return
        
        stats = self.db.get_stats()
        message = MessageTemplates.admin_stats(stats)
        await update.message.reply_text(message)
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users - Command: /broadcast message"""
        if not self.is_admin(update.effective_user.id):
            return
        
        if not context.args:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/broadcast message\n\nمثال: /broadcast مرحباً بكم جميعاً!"
            )
            return
        
        message = ' '.join(context.args)
        users = self.db.get_all_users()
        
        await update.message.reply_text(f"📡 بدء البث لـ {len(users)} مستخدم...")
        
        success_count = 0
        for user_id in users:
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
                success_count += 1
                
                # Small delay to avoid rate limiting
                if success_count % 20 == 0:
                    await asyncio.sleep(1)
                    
            except TelegramError:
                continue  # User blocked bot or deleted account
        
        await update.message.reply_text(f"✅ تم البث بنجاح لـ {success_count} من أصل {len(users)} مستخدم")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin callback queries"""
        if not self.is_admin(update.effective_user.id):
            return
        
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "admin_menu":
            await self.admin_menu(update, context)
        elif data == "admin_stats":
            stats = self.db.get_stats()
            message = MessageTemplates.admin_stats(stats)
            await query.edit_message_text(message, reply_markup=admin_back_keyboard())
        elif data == "admin_orders":
            orders = self.db.get_orders()
            message = MessageTemplates.order_list(orders)
            await query.edit_message_text(message, reply_markup=admin_back_keyboard())
        elif data == "admin_users":
            await self._handle_admin_users(query, context)
        elif data == "admin_channels":
            await self._handle_admin_channels(query, context)
        elif data == "admin_codes":
            await self._handle_admin_codes(query, context)
        elif data == "admin_broadcast":
            await self._handle_admin_broadcast(query, context)
        elif data == "admin_add_normal_channel":
            await self._handle_admin_add_channel_prompt(query, context, 'normal')
        elif data == "admin_add_vip_channel":
            await self._handle_admin_add_channel_prompt(query, context, 'vip')
        elif data == "admin_remove_channel":
            await self._handle_admin_remove_channel_prompt(query, context)
        elif data == "admin_add_points":
            await self._handle_admin_add_points_prompt(query, context)
        elif data == "admin_remove_points":
            await self._handle_admin_remove_points_prompt(query, context)
        elif data == "admin_ban_user":
            await self._handle_admin_ban_user_prompt(query, context)
        elif data == "admin_unban_user":
            await self._handle_admin_unban_user_prompt(query, context)
        elif data == "admin_mandatory_channels":
            await self._handle_admin_mandatory_channels(query, context)
        elif data == "admin_add_mandatory":
            await self._handle_admin_add_mandatory_prompt(query, context)
        elif data == "admin_remove_mandatory":
            await self._handle_admin_remove_mandatory_prompt(query, context)
        elif data == "admin_user_info":
            await self._handle_admin_user_info_prompt(query, context)

    
    async def _handle_admin_users(self, query, context):
        """Handle admin users management"""
        stats = self.db.get_stats()
        message = f"👥 إدارة المستخدمين\n\nإجمالي المستخدمين: {stats['users']}\n\nاستخدم الأوامر التالية:\n/addpoints معرف_المستخدم النقاط\n/removepoints معرف_المستخدم النقاط"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_channels(self, query, context):
        """Handle admin channels management"""
        channels = self.db.get_active_channels()
        
        if not channels:
            message = "📢 لا توجد قنوات نشطة"
        else:
            message = "📢 القنوات النشطة:\n\n"
            for channel in channels[:10]:  # Show only first 10
                status = "🟢" if channel['active'] else "🔴"
                progress = f"{channel['gained']}/{channel['target']}"
                message += f"{status} @{channel['username']} - {channel['type']}\nالتقدم: {progress}\n\n"
        
        message += "\n💡 الأوامر المتاحة:\n/addchannel @قناة نوع هدف\n/removechannel @قناة"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_codes(self, query, context):
        """Handle admin codes management"""
        message = "🎟️ إدارة أكواد الهدايا\n\n💡 لإنشاء كود جديد:\n/makecode الكود النقاط الحد_الأقصى\n\nمثال:\n/makecode GIFT100 100 50"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_broadcast(self, query, context):
        """Handle admin broadcast"""
        message = "📣 بث رسالة جماعية\n\n💡 لبث رسالة لجميع المستخدمين:\n/broadcast النص\n\nمثال:\n/broadcast مرحباً بكم جميعاً في البوت!"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_add_channel_prompt(self, query, context, channel_type='normal'):
        """Prompt admin to add channel"""
        message = "➕ إضافة قناة جديدة\n\n💡 الأمر:\n/addchannel @اسم_القناة نوع هدف\n\nالأنواع المتاحة:\n• normal - قناة عادية (3 نقاط)\n• vip - قناة VIP (4 نقاط)\n\nمثال:\n/addchannel @mychannel vip 1000"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
        
        context.user_data['awaiting_admin_action'] = 'add_channel'
    
    async def _handle_admin_remove_channel_prompt(self, query, context):
        """Prompt admin to remove channel"""
        message = "➖ حذف قناة\n\n💡 الأمر:\n/removechannel @اسم_القناة\n\nمثال:\n/removechannel @mychannel"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
        
        context.user_data['awaiting_admin_action'] = 'remove_channel'
    
    async def _handle_admin_add_points_prompt(self, query, context):
        """Prompt admin to add points"""
        message = "💰 إضافة نقاط\n\n💡 الأمر:\n/addpoints معرف_المستخدم النقاط\n\nمثال:\n/addpoints 123456789 100"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
        
        context.user_data['awaiting_admin_action'] = 'add_points'
    
    async def _handle_admin_remove_points_prompt(self, query, context):
        """Prompt admin to remove points"""
        message = "🚫 خصم نقاط\n\n💡 الأمر:\n/removepoints معرف_المستخدم النقاط\n\nمثال:\n/removepoints 123456789 50"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
        
        context.user_data['awaiting_admin_action'] = 'remove_points'
    
    async def handle_admin_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin text messages when expecting admin input"""
        if not self.is_admin(update.effective_user.id):
            return
        
        action = context.user_data.get('awaiting_admin_action')
        if not action:
            return
        
        # Clear the waiting state
        context.user_data.pop('awaiting_admin_action', None)
        
        text = update.message.text.strip()
        
        if action == 'add_channel':
            # Parse add channel command
            parts = text.split()
            if len(parts) != 3:
                await update.message.reply_text("❌ تنسيق خاطئ. استخدم: @اسم_القناة نوع هدف")
                return
            
            channel_username = parts[0].replace('@', '')
            channel_type = parts[1].lower()
            
            if channel_type not in ['normal', 'vip']:
                await update.message.reply_text("❌ النوع يجب أن يكون: normal أو vip")
                return
            
            try:
                target = int(parts[2])
            except ValueError:
                await update.message.reply_text("❌ الهدف يجب أن يكون رقم صحيح")
                return
            
            # Admin commands are free - no payment required
            price = 0  # Free for admin
            
            # Create order first (free for admin)
            order_id = self.db.create_order(update.effective_user.id, channel_username, price, target)
            
            if order_id and self.db.add_channel(channel_username, channel_type, target, order_id):
                message = f"✅ تم إضافة القناة @{channel_username} من نوع {channel_type}\nالهدف: {target} عضو\n💰 السعر: {price} نقطة\n🆔 رقم الطلب: {order_id}"
            else:
                message = "❌ القناة موجودة مسبقاً أو حدث خطأ"
            
            await update.message.reply_text(message)
        
        elif action == 'remove_channel':
            # Parse remove channel command
            channel_username = text.replace('@', '')
            
            if self.db.remove_channel(channel_username):
                message = f"✅ تم حذف القناة @{channel_username}"
            else:
                message = "❌ القناة غير موجودة"
            
            await update.message.reply_text(message)
        
        elif action in ['add_points', 'remove_points']:
            # Parse points command
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("❌ تنسيق خاطئ. استخدم: معرف_المستخدم النقاط")
                return
            
            try:
                user_id = int(parts[0])
                points = int(parts[1])
            except ValueError:
                await update.message.reply_text("❌ يجب أن يكون معرف المستخدم والنقاط أرقام صحيحة")
                return
            
            if action == 'remove_points':
                points = -points
            
            if self.db.update_user_points(user_id, points):
                action_text = "إضافة" if points > 0 else "خصم"
                message = f"✅ تم {action_text} {abs(points)} نقطة للمستخدم {user_id}"
            else:
                message = "❌ المستخدم غير موجود"
            
            await update.message.reply_text(message)
    
    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban user by username - Command: /ban @username"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ الاستخدام الصحيح:\n/ban @username\n\nمثال: /ban @baduser")
            return
        
        username = args[0].replace('@', '')
        
        # Get user ID by username (if user exists in database)
        user_data = self.db.get_user_by_username(username)
        if not user_data:
            await update.message.reply_text(f"❌ المستخدم @{username} غير موجود في قاعدة البيانات")
            return
        
        user_id = user_data['id']
        
        if self.db.ban_user(user_id, f"Banned by admin via username @{username}"):
            message = f"🔨 تم حظر المستخدم @{username} (ID: {user_id}) بنجاح"
        else:
            message = "❌ حدث خطأ في حظر المستخدم"
        
        await update.message.reply_text(message)
    
    async def unban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban user by username - Command: /unban @username"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ الاستخدام الصحيح:\n/unban @username\n\nمثال: /unban @gooduser")
            return
        
        username = args[0].replace('@', '')
        
        # Get user ID by username (if user exists in database)
        user_data = self.db.get_user_by_username(username)
        if not user_data:
            await update.message.reply_text(f"❌ المستخدم @{username} غير موجود في قاعدة البيانات")
            return
        
        user_id = user_data['id']
        
        if self.db.unban_user(user_id):
            message = f"✅ تم إلغاء حظر المستخدم @{username} (ID: {user_id}) بنجاح"
        else:
            message = "❌ حدث خطأ في إلغاء حظر المستخدم"
        
        await update.message.reply_text(message)
    
    async def add_mandatory_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add mandatory channel - Command: /addmandatory @channel [title]"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ الاستخدام الصحيح:\n/addmandatory @channel [title]\n\nمثال: /addmandatory @mychannel قناة التحديثات")
            return
        
        channel_username = args[0].replace('@', '')
        channel_title = ' '.join(args[1:]) if len(args) > 1 else None
        
        if self.db.add_mandatory_channel(channel_username, channel_title):
            message = f"✅ تمت إضافة القناة @{channel_username} كقناة إجبارية"
            if channel_title:
                message += f"\nالعنوان: {channel_title}"
        else:
            message = "❌ حدث خطأ في إضافة القناة الإجبارية"
        
        await update.message.reply_text(message)
    
    async def remove_mandatory_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove mandatory channel - Command: /removemandatory @channel"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ الاستخدام الصحيح:\n/removemandatory @channel\n\nمثال: /removemandatory @mychannel")
            return
        
        channel_username = args[0].replace('@', '')
        
        if self.db.remove_mandatory_channel(channel_username):
            message = f"✅ تم حذف القناة @{channel_username} من القنوات الإجبارية"
        else:
            message = "❌ حدث خطأ في حذف القناة الإجبارية أو أنها غير موجودة"
        
        await update.message.reply_text(message)
    
    async def _handle_admin_ban_user_prompt(self, query, context):
        """Prompt admin to ban user"""
        message = "🔨 حظر مستخدم\n\n💡 الأمر:\n/ban @اسم_المستخدم\n\nمثال:\n/ban @baduser"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_unban_user_prompt(self, query, context):
        """Prompt admin to unban user"""
        message = "✅ إلغاء حظر مستخدم\n\n💡 الأمر:\n/unban @اسم_المستخدم\n\nمثال:\n/unban @gooduser"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_mandatory_channels(self, query, context):
        """Show mandatory channels management"""
        channels = self.db.get_mandatory_channels()
        
        if not channels:
            message = "🔒 لا توجد قنوات إجبارية مُضافة\n\n💡 القنوات الإجبارية هي قنوات يجب على جميع المستخدمين الاشتراك فيها قبل استخدام البوت"
        else:
            message = "🔒 القنوات الإجبارية النشطة:\n\n"
            for channel in channels:
                message += f"📢 @{channel['channel_username']}\n"
                if channel['channel_title']:
                    message += f"📝 {channel['channel_title']}\n"
                message += f"📅 أُضيفت: {channel['added_at'][:10]}\n\n"
        
        message += "\n💡 استخدم الأزرار لإضافة أو حذف قنوات إجبارية"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_add_mandatory_prompt(self, query, context):
        """Prompt admin to add mandatory channel"""
        message = "➕ إضافة قناة إجبارية\n\n💡 الأمر:\n/addmandatory @اسم_القناة [عنوان_اختياري]\n\nمثال:\n/addmandatory @mychannel قناة التحديثات"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_remove_mandatory_prompt(self, query, context):
        """Prompt admin to remove mandatory channel"""
        message = "➖ حذف قناة إجبارية\n\n💡 الأمر:\n/removemandatory @اسم_القناة\n\nمثال:\n/removemandatory @mychannel"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def _handle_admin_user_info_prompt(self, query, context):
        """Prompt admin to search for user info"""
        message = "🔍 البحث عن معلومات المستخدم\n\n💡 الأمر:\n/userinfo @اسم_المستخدم\n\nمثال:\n/userinfo @john123"
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def get_user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user info by username - Command: /userinfo @username"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = context.args
        if not args:
            await update.message.reply_text("❌ الاستخدام الصحيح:\n/userinfo @username\n\nمثال: /userinfo @john123")
            return
        
        username = args[0].replace('@', '')
        
        # Search for user by username
        user_info = self.db.get_user_by_username(username)
        
        if not user_info:
            await update.message.reply_text(f"❌ لم يتم العثور على مستخدم بالاسم @{username}")
            return
        
        # Get user subscriptions
        subscriptions = self.db.get_user_subscriptions(user_info['id'])
        subscription_count = len(subscriptions)
        
        # Check if user is banned
        is_banned = self.db.is_user_banned(user_info['id'])
        ban_info = ""
        if is_banned:
            ban_data = self.db.get_ban_info(user_info['id'])
            ban_info = f"\n🚫 المستخدم محظور\n📝 سبب الحظر: {ban_data.get('reason', 'غير محدد')}"
        
        # Format message
        message = f"👤 معلومات المستخدم @{username}\n\n"
        message += f"🆔 ID: {user_info['id']}\n"
        message += f"👤 الاسم: {user_info['first_name']}\n"
        if user_info.get('username'):
            message += f"📱 المعرف: @{user_info['username']}\n"
        message += f"💰 النقاط: {user_info['points']}\n"
        message += f"📊 الاشتراكات النشطة: {subscription_count}\n"
        if user_info.get('referred_by'):
            message += f"👥 تم دعوته بواسطة: {user_info['referred_by']}\n"
        message += f"📅 تاريخ التسجيل: {user_info['joined_at'][:10]}\n"
        message += ban_info
        
        # Show subscriptions if any
        if subscriptions:
            message += f"\n📢 القنوات المشترك بها:\n"
            for sub in subscriptions:
                message += f"• @{sub}\n"
        
        await update.message.reply_text(message)
    
    async def _handle_admin_special_content(self, query, context):
        """Handle special content management"""
        special_content = self.db.get_special_content()
        
        if not special_content:
            message = "💬 إدارة المحتوى الخاص\n\n❌ لا يوجد محتوى خاص مُضاف\n\n"
            message += "💡 المحتوى الخاص يُعرض فقط للمستخدمين الذين:\n"
            message += "• لم يشتركوا في أي قناة\n"
            message += "• أو اشتركوا ثم غادروا القنوات (مع خصم 5 نقاط)\n\n"
            message += "📝 لإضافة محتوى خاص جديد:\n"
            message += "/addcontent العنوان | النص\n\n"
            message += "مثال:\n/addcontent رسالة ترحيب | مرحباً بك في المحتوى الخاص"
        else:
            message = "💬 إدارة المحتوى الخاص\n\n"
            message += f"📊 إجمالي المحتوى: {len(special_content)}\n\n"
            
            for i, content in enumerate(special_content[:5], 1):  # Show first 5
                message += f"📝 {i}. **{content['content_title']}**\n"
                content_preview = content['content_message'][:50] + "..." if len(content['content_message']) > 50 else content['content_message']
                message += f"💭 {content_preview}\n"
                message += f"📅 {content['created_at'][:10]}\n\n"
            
            if len(special_content) > 5:
                message += f"💡 و {len(special_content) - 5} محتوى إضافي...\n\n"
            
            message += "📝 لإضافة محتوى جديد:\n/addcontent العنوان | النص"
        
        await query.edit_message_text(message, reply_markup=admin_back_keyboard())
    
    async def add_special_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add special content - Command: /addcontent title | content"""
        if not self.is_admin(update.effective_user.id):
            return
        
        args = ' '.join(context.args) if context.args else ''
        if not args or '|' not in args:
            await update.message.reply_text(
                "❌ الاستخدام الصحيح:\n/addcontent العنوان | النص\n\n"
                "مثال:\n/addcontent رسالة ترحيب | مرحباً بك في المحتوى الخاص!"
            )
            return
        
        try:
            title, content = args.split('|', 1)
            title = title.strip()
            content = content.strip()
            
            if not title or not content:
                await update.message.reply_text("❌ يجب ملء العنوان والنص")
                return
            
            success = self.db.add_special_content(title, content)
            
            if success:
                message = f"✅ تم إضافة المحتوى الخاص بنجاح!\n\n📝 العنوان: {title}\n💭 النص: {content[:100]}{'...' if len(content) > 100 else ''}"
            else:
                message = "❌ حدث خطأ في إضافة المحتوى الخاص"
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logging.error(f"Error adding special content: {e}")
            await update.message.reply_text("❌ حدث خطأ في معالجة الأمر")
