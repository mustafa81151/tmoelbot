import logging
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import TelegramError

from database import Database
from keyboards import *
from config import *
from utils import *
from user_verification import check_user_legitimacy

class BotHandlers:
    def __init__(self, database: Database):
        self.db = database
        self.bot_username = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with mandatory channels check"""
        user = update.effective_user
        user_id = user.id
        
        # Extract referrer ID from command
        referred_by = extract_user_id_from_start(update.message.text)
        
        # Check if user is new (not in database)
        is_new_user = not self.db.get_user(user_id)
        
        # Security check for new users only
        if is_new_user:
            # Check if user has already passed verification
            if not context.user_data.get('verified', False):
                await self._handle_user_verification(update, context, referred_by)
                return
        
        # Add user to database
        user_added = self.db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by=referred_by
        )
        
        # Award referral points if user was referred and is new
        if user_added and referred_by and referred_by != user.id:
            self.db.update_user_points(referred_by, REFERRAL_POINTS)
            
            # Notify referrer
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 تم قبول دعوتك!\nحصلت على {REFERRAL_POINTS} نقطة من دعوة @{user.username or user.first_name}"
                )
            except TelegramError:
                pass
        
        # Get bot username for referral links
        if not self.bot_username:
            bot_info = await context.bot.get_me()
            self.bot_username = bot_info.username
        
        # Check mandatory channels for all users (including returning ones)
        mandatory_channels = self.db.get_mandatory_channels()
        if mandatory_channels:
            from utils import check_mandatory_channels_membership
            all_subscribed, missing_channels = await check_mandatory_channels_membership(
                context.bot, user_id, mandatory_channels
            )
            
            if not all_subscribed:
                # Show mandatory channels message
                welcome_msg = "👋 أهلاً وسهلاً!\n\n🔒 للاستمرار، يجب الاشتراك في القنوات التالية:\n\n"
                for channel in missing_channels:
                    channel_link = f"https://t.me/{channel['channel_username']}"
                    welcome_msg += f"📢 @{channel['channel_username']}\n"
                    if channel.get('channel_title'):
                        welcome_msg += f"📝 {channel['channel_title']}\n"
                    welcome_msg += f"{channel_link}\n\n"
                welcome_msg += "✅ بعد الاشتراك، اضغط /start مرة أخرى"
                
                await update.message.reply_text(welcome_msg)
                return
        
        # Admin notification removed - only send for genuinely new users in _complete_user_registration

        # Welcome message for new or returning users
        if is_new_user:
            welcome_text = "🎉 مرحباً بك في بوت تجميع النقاط!\n\n📊 يمكنك كسب النقاط من خلال:\n• الانضمام للقنوات\n• دعوة الأصدقاء\n• المكافآت اليومية\n\n🛒 استخدم النقاط لشراء أعضاء لقناتك"
        else:
            user_data = self.db.get_user(user_id)
            welcome_text = f"👋 أهلاً بعودتك!\n\n💰 رصيدك: {user_data['points']} نقطة"
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=main_keyboard()
        )

    async def _handle_user_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE, referred_by=None):
        """Handle new user verification with security check"""
        import random
        
        # Generate random 4-digit number
        verification_code = random.randint(1000, 9999)
        
        # Store in user context
        context.user_data['verification_code'] = verification_code
        context.user_data['verification_attempts'] = 0
        context.user_data['awaiting_verification'] = True
        context.user_data['referred_by'] = referred_by
        
        verification_msg = f"🔐 **تحقق أمني**\n\n"
        verification_msg += f"مرحباً {update.effective_user.first_name}!\n\n"
        verification_msg += f"للتأكد من أنك شخص حقيقي، يرجى كتابة الرقم التالي:\n\n"
        verification_msg += f"**{verification_code}**\n\n"
        verification_msg += f"⚠️ اكتب الرقم بالضبط كما هو موضح أعلاه"
        
        await update.message.reply_text(verification_msg, parse_mode='Markdown')
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        # Check if user is banned
        if self.db.is_user_banned(user_id):
            await query.edit_message_text("🚫 تم حظرك من استخدام البوت")
            return
        
        # Ensure user exists in database
        self.db.add_user(user_id, query.from_user.username, query.from_user.first_name)
        
        if data == "account":
            await self._handle_account(query, user_id)
        elif data == "daily_reward":
            await self._handle_daily_reward(query, user_id)
        elif data == "referral":
            await self._handle_referral(query, user_id, context)
        elif data == "channels":
            await self._handle_channels(query, context)
        elif data == "vip_channels":
            await self._handle_vip_channels(query, context)
        elif data == "refresh_channels":
            await self._handle_refresh_channels(query, context)
        elif data == "refresh_vip_channels":
            await self._handle_refresh_vip_channels(query, context)
        elif data == "shop":
            await self._handle_shop(query)
        elif data.startswith("buy_"):
            await self._handle_buy(query, user_id, data, context)
        elif data.startswith("join_"):
            await self._handle_join_channel(query, user_id, data, context)
        elif data.startswith("confirm_"):
            await self._handle_confirmation(query, user_id, data, context)
        elif data == "back_to_main":
            await self._handle_back_to_main(query)
        elif data == "redeem_code":
            await self._handle_redeem_code_prompt(query, context)

    
    async def _handle_account(self, query, user_id):
        """Handle account information request"""
        user_data = self.db.get_user(user_id)
        if user_data:
            message = MessageTemplates.user_stats(user_data)
            await query.edit_message_text(message, reply_markup=back_keyboard())
    
    async def _handle_daily_reward(self, query, user_id):
        """Handle daily reward claim"""
        if self.db.can_claim_daily_reward(user_id):
            if self.db.claim_daily_reward(user_id, DAILY_REWARD_POINTS):
                message = MESSAGES['daily_reward_claimed'].format(points=DAILY_REWARD_POINTS)
            else:
                message = "❌ حدث خطأ، حاول مرة أخرى"
        else:
            message = MESSAGES['daily_reward_already_claimed']
        
        await query.edit_message_text(message, reply_markup=back_keyboard())
    
    async def _handle_referral(self, query, user_id, context):
        """Handle referral link generation"""
        if not self.bot_username:
            bot_info = await context.bot.get_me()
            self.bot_username = bot_info.username
        
        referral_link = generate_referral_link(self.bot_username, user_id)
        message = MESSAGES['referral_link'].format(link=referral_link, points=REFERRAL_POINTS)
        
        await query.edit_message_text(message, reply_markup=back_keyboard())
    
    async def _handle_channels(self, query, context=None):
        """Handle normal channels list display with smart filtering"""
        user_id = query.from_user.id
        
        # Verify user's current subscriptions if context is available
        if context:
            await self._verify_user_subscriptions(context.bot, user_id)
        
        # Get normal channels only
        all_channels = self.db.get_active_channels('normal')
        user_subscriptions = self.db.get_user_subscriptions(user_id)
        
        logging.info(f"Available normal channels: {len(all_channels)}, User subscriptions: {user_subscriptions}")
        
        # Smart filtering: Show channels the user can join
        channels = []
        for channel in all_channels:
            if channel['username'] not in user_subscriptions:
                # User has never joined this channel via bot - show it
                channels.append(channel)
                logging.info(f"Showing channel @{channel['username']} - user not subscribed")
            elif context:
                # User has subscription record - check if they're still actually in the channel
                is_still_member = await check_user_membership(context.bot, user_id, channel['username'])
                if not is_still_member:
                    # User left but record exists - clean up and allow re-joining
                    self.db.penalize_channel_leaver(user_id, channel['username'], 0)
                    channels.append(channel)
                    logging.info(f"Showing channel @{channel['username']} - user returned externally")
                else:
                    logging.info(f"Hiding channel @{channel['username']} - user still subscribed and present")
        
        if not channels:
            await query.edit_message_text("📢 لا توجد قنوات عادية متاحة للانضمام حالياً", reply_markup=back_keyboard())
            return
        
        message = f"📢 القنوات العادية ({len(channels)} متاحة):\n\n"
        message += "💰 كل قناة تمنحك 3 نقاط\n\n"
        
        # Add status info for user
        subscribed_count = len([ch for ch in channels if ch['username'] in user_subscriptions])
        if subscribed_count > 0:
            message += f"✅ أنت مشترك في {subscribed_count} قناة\n"
        message += "👆 اختر قناة:"
        
        await query.edit_message_text(message, reply_markup=channels_keyboard(channels))
    
    async def _handle_vip_channels(self, query, context=None):
        """Handle VIP channels list display"""
        user_id = query.from_user.id
        
        # Verify user's current subscriptions if context is available
        if context:
            await self._verify_user_subscriptions(context.bot, user_id)
        
        # Get VIP channels only
        all_channels = self.db.get_active_channels('vip')
        user_subscriptions = self.db.get_user_subscriptions(user_id)
        
        logging.info(f"Available VIP channels: {len(all_channels)}, User subscriptions: {user_subscriptions}")
        
        # Smart filtering: Show channels the user can join
        channels = []
        for channel in all_channels:
            if channel['username'] not in user_subscriptions:
                # User has never joined this channel via bot - show it
                channels.append(channel)
                logging.info(f"Showing VIP channel @{channel['username']} - user not subscribed")
            elif context:
                # User has subscription record - check if they're still actually in the channel
                is_still_member = await check_user_membership(context.bot, user_id, channel['username'])
                if not is_still_member:
                    # User left but record exists - clean up and allow re-joining
                    self.db.penalize_channel_leaver(user_id, channel['username'], 0)
                    channels.append(channel)
                    logging.info(f"Showing VIP channel @{channel['username']} - user returned externally")
                else:
                    logging.info(f"Hiding VIP channel @{channel['username']} - user still subscribed and present")
        
        if not channels:
            await query.edit_message_text("⭐ لا توجد قنوات VIP متاحة للانضمام حالياً", reply_markup=back_keyboard())
            return
        
        message = "⭐ قنوات VIP المتاحة للانضمام:\n\n"
        for channel in channels:
            progress = f"{channel['gained']}/{channel['target']}"
            message += f"@{channel['username']} - VIP ⭐ ({VIP_CHANNEL_POINTS} نقاط)\nالتقدم: {progress}\n\n"
        
        await query.edit_message_text(message, reply_markup=vip_channels_keyboard(channels))
    
    async def _handle_refresh_channels(self, query, context):
        """Handle channels refresh with member count update"""
        user_id = query.from_user.id
        all_channels = self.db.get_active_channels()
        
        # Update member counts and check for leavers for all channels
        for channel in all_channels:
            # Check for users who left the channel and penalize them (5 points penalty)
            await self._check_channel_leavers(context.bot, channel['username'])
            
            # Update channel member count
            completed = self.db.update_channel_members(channel['username'])  # Smart bot-only counting
            if completed:
                # Channel completed, log it
                logging.info(f"✅ Channel @{channel['username']} completed its target during refresh")
        
        # Get updated channels available for this user (with real-time checking)
        all_channels = self.db.get_available_channels_for_user(user_id)
        user_subscriptions = self.db.get_user_subscriptions(user_id)
        
        # Smart filtering: Show channels the user can join
        channels = []
        for channel in all_channels:
            if channel['username'] not in user_subscriptions:
                # User has never joined this channel via bot - show it
                channels.append(channel)
            else:
                # User has subscription record - check if they're still actually in the channel
                is_still_member = await check_user_membership(context.bot, user_id, channel['username'])
                if not is_still_member:
                    # User left but record exists - clean up and allow re-joining
                    self.db.penalize_channel_leaver(user_id, channel['username'], 0)
                    channels.append(channel)
        
        if not channels:
            await query.edit_message_text("📢 لا توجد قنوات متاحة للانضمام حالياً\n\n🔄 تم تحديث عدد الأعضاء", reply_markup=back_keyboard())
            return
        
        message = "📢 القنوات المتاحة للانضمام:\n\n"
        for channel in channels:
            channel_type = "VIP ⭐" if channel['type'] == 'vip' else "عادية"
            points = VIP_CHANNEL_POINTS if channel['type'] == 'vip' else NORMAL_CHANNEL_POINTS
            progress = f"{channel['gained']}/{channel['target']}"
            message += f"@{channel['username']} - {channel_type} ({points} نقاط)\nالتقدم: {progress}\n\n"
        
        message += "\n🔄 تم تحديث عدد الأعضاء"
        await query.edit_message_text(message, reply_markup=channels_keyboard(channels))
    
    async def _handle_refresh_vip_channels(self, query, context):
        """Handle VIP channels refresh"""
        user_id = query.from_user.id
        all_channels = self.db.get_active_channels('vip')
        
        # Update member counts and check for leavers for VIP channels
        for channel in all_channels:
            await self._check_channel_leavers(context.bot, channel['username'])
            completed = self.db.update_channel_members(channel['username'])
            if completed:
                logging.info(f"✅ VIP Channel @{channel['username']} completed its target during refresh")
        
        # Get updated VIP channels
        all_channels = self.db.get_active_channels('vip')
        user_subscriptions = self.db.get_user_subscriptions(user_id)
        
        channels = []
        for channel in all_channels:
            if channel['username'] not in user_subscriptions:
                channels.append(channel)
            else:
                is_still_member = await check_user_membership(context.bot, user_id, channel['username'])
                if not is_still_member:
                    self.db.penalize_channel_leaver(user_id, channel['username'], 0)
                    channels.append(channel)
        
        if not channels:
            await query.edit_message_text("⭐ لا توجد قنوات VIP متاحة للانضمام حالياً\n\n🔄 تم تحديث عدد الأعضاء", reply_markup=back_keyboard())
            return
        
        message = "⭐ قنوات VIP المتاحة للانضمام:\n\n"
        for channel in channels:
            progress = f"{channel['gained']}/{channel['target']}"
            message += f"@{channel['username']} - VIP ⭐ ({VIP_CHANNEL_POINTS} نقاط)\nالتقدم: {progress}\n\n"
        
        message += "\n🔄 تم تحديث عدد الأعضاء"
        await query.edit_message_text(message, reply_markup=vip_channels_keyboard(channels))
    
    async def _handle_shop(self, query):
        """Handle shop display"""
        message = "🛒 متجر شراء الأعضاء:\n\nاختر الباقة المناسبة لك:\n\n"
        for members, points in SHOP_PRICES.items():
            message += f"• {members} عضو = {points} نقطة\n"
        
        await query.edit_message_text(message, reply_markup=shop_keyboard())
    
    async def _handle_buy(self, query, user_id, data, context):
        """Handle buy request"""
        members_count = int(data.split('_')[1])
        points_cost = SHOP_PRICES[members_count]
        
        user_data = self.db.get_user(user_id)
        if not user_data or user_data['points'] < points_cost:
            current_points = user_data['points'] if user_data else 0
            message = MESSAGES['insufficient_points'].format(required=points_cost, current=current_points)
            await query.edit_message_text(message, reply_markup=back_keyboard())
            return
        
        # Ask for channel username
        message = f"📝 أرسل username القناة التي تريد شراء {members_count} عضو لها\n\n" \
                 f"💰 التكلفة: {points_cost} نقطة\n" \
                 f"مثال: @mychannel"
        
        await query.edit_message_text(message, reply_markup=back_keyboard())
        
        # Store purchase data in user context
        context.user_data['purchase_data'] = {
            'members_count': members_count,
            'points_cost': points_cost,
            'awaiting_channel': True
        }
    
    async def _handle_join_channel(self, query, user_id, data, context):
        """Handle channel join verification"""
        channel_username = data.split('_', 1)[1]
        
        # First check if user already joined this channel via bot
        user_subscriptions = self.db.get_user_subscriptions(user_id)
        if channel_username in user_subscriptions:
            message = "⚠️ لقد انضممت لهذه القناة مسبقاً وحصلت على النقاط"
            await query.edit_message_text(message, reply_markup=back_keyboard())
            return
        
        # Check if user is actually a real member of the channel (not fake account)
        is_member = await check_user_membership(context.bot, user_id, channel_username)
        
        if not is_member:
            message = f"❌ يجب الانضمام للقناة @{channel_username} أولاً\n\n⚠️ تأكد من أن حسابك حقيقي وليس مزيف"
            await query.edit_message_text(message, reply_markup=back_keyboard())
            return
        
        # Get channel info and award points
        channels = self.db.get_active_channels()
        channel_info = next((c for c in channels if c['username'] == channel_username), None)
        
        if not channel_info:
            await query.edit_message_text("❌ القناة غير متاحة", reply_markup=back_keyboard())
            return
        
        points = VIP_CHANNEL_POINTS if channel_info['type'] == 'vip' else NORMAL_CHANNEL_POINTS
        
        # Record the join and award points - user is confirmed to be a new legitimate member
        success = self.db.user_joined_channel(user_id, channel_username, points)
        
        if success:
            # Update channel count immediately - smart counting of bot users only
            completed, order_owner_id = self.db.update_channel_members(channel_username)
            
            # Send notification to order owner about new member
            if order_owner_id and order_owner_id != user_id:
                user_info = self.db.get_user(user_id)
                user_name = f"@{user_info['username']}" if user_info.get('username') else user_info['first_name']
                
                try:
                    await context.bot.send_message(
                        chat_id=order_owner_id,
                        text=f"🎉 عضو جديد انضم لقناتك!\n\n"
                             f"📢 القناة: @{channel_username}\n"
                             f"👤 العضو الجديد: {user_name}\n"
                             f"🆔 معرف المستخدم: {user_id}\n"
                             f"📊 معلومات إضافية: {user_info['points']} نقطة، انضم في {user_info['joined_at'][:10]}"
                    )
                except Exception as e:
                    logging.error(f"Failed to notify order owner {order_owner_id}: {e}")
            
            if completed:
                message = f"🎉 تم كسب {points} نقطة!\n✅ القناة وصلت للهدف المطلوب وتم إكمال الطلب!"
                
                # Notify admin and order owner about completion
                try:
                    completion_message = f"🎯 تم إكمال طلب!\n\n📢 القناة: @{channel_username}\n✅ تم الوصول للهدف المطلوب"
                    
                    # Notify admin
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=completion_message
                    )
                    
                    # Notify order owner if different from admin
                    if order_owner_id and order_owner_id != ADMIN_ID:
                        await context.bot.send_message(
                            chat_id=order_owner_id,
                            text=f"🎉 تهانينا! تم إكمال طلبك!\n\n📢 القناة: @{channel_username}\n✅ تم الوصول للعدد المطلوب من الأعضاء\n\n🙏 شكراً لاستخدام خدماتنا"
                        )
                except Exception as e:
                    logging.error(f"Failed to send completion notifications: {e}")
                
                logging.info(f"✅ Channel @{channel_username} completed its target and was deactivated")
            else:
                # Get updated channel info to show real progress
                channels = self.db.get_active_channels()
                channel_info = next((c for c in channels if c['username'] == channel_username), None)
                if channel_info:
                    progress = f"{channel_info['gained']}/{channel_info['target']}"
                    message = f"🎉 تم كسب {points} نقطة!\n📊 التقدم الحالي: {progress}\n\n✅ تم التحقق من صحة حسابك"
                else:
                    message = f"🎉 تم كسب {points} نقطة!\n✅ تم التحقق من صحة حسابك"
        else:
            message = "❌ حدث خطأ في تسجيل انضمامك، حاول مرة أخرى"
        
        await query.edit_message_text(message, reply_markup=back_keyboard())
    
    async def _verify_user_subscriptions(self, bot, user_id):
        """Verify and clean up a specific user's channel subscriptions"""
        try:
            # Get all channels this user is subscribed to in the database
            user_subscriptions = self.db.get_user_subscriptions(user_id)
            
            for channel_username in user_subscriptions:
                # Check if user is still actually a member
                is_member = await check_user_membership(bot, user_id, channel_username)
                if not is_member:
                    # User left the channel, penalize them
                    self.db.penalize_channel_leaver(user_id, channel_username, 5)
                    logging.info(f"✅ User {user_id} penalized for leaving channel @{channel_username} (5 points deducted)")
                    
        except Exception as e:
            logging.error(f"Error verifying user {user_id} subscriptions: {e}")

    async def _check_channel_leavers(self, bot, channel_username):
        """Check for users who left the channel and penalize them"""
        try:
            # Get all users who joined this channel
            joined_users = self.db.get_channel_subscribers(channel_username)
            
            for user_id in joined_users:
                # Check if user is still a member
                is_member = await check_user_membership(bot, user_id, channel_username)
                if not is_member:
                    # User left the channel, penalize them
                    self.db.penalize_channel_leaver(user_id, channel_username, 5)
                    
        except Exception as e:
            logging.error(f"Error checking channel leavers for {channel_username}: {e}")
    
    async def _handle_confirmation(self, query, user_id, data, context):
        """Handle confirmation actions"""
        parts = data.split('_', 2)
        if len(parts) != 3:
            return
        
        action = parts[1]
        action_data = parts[2]
        
        if action == "buy" and context.user_data.get('purchase_data'):
            purchase_data = context.user_data['purchase_data']
            channel_username = action_data
            
            # Create order
            # Get current member count as initial count
            initial_count = await get_channel_member_count(context.bot, channel_username)
            
            order_id = self.db.create_order(
                user_id=user_id,
                channel_username=channel_username,
                members_count=purchase_data['members_count'],
                points_cost=purchase_data['points_cost'],
                initial_count=initial_count
            )
            
            if order_id:
                # Clear purchase data
                context.user_data.pop('purchase_data', None)
                
                # Send admin notification about purchase
                try:
                    buyer_info = self.db.get_user(user_id)
                    admin_purchase_msg = f"💰 طلب شراء جديد!\n\n"
                    admin_purchase_msg += f"👤 المشتري: {buyer_info['first_name']}\n"
                    if buyer_info.get('username'):
                        admin_purchase_msg += f"📱 المعرف: @{buyer_info['username']}\n"
                    admin_purchase_msg += f"🆔 ID: {user_id}\n"
                    admin_purchase_msg += f"📢 القناة: @{channel_username}\n"
                    admin_purchase_msg += f"👥 عدد الأعضاء: {purchase_data['members_count']}\n"
                    admin_purchase_msg += f"💎 النقاط المدفوعة: {purchase_data['points_cost']}\n"
                    admin_purchase_msg += f"🆔 رقم الطلب: #{order_id}"
                    
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=admin_purchase_msg
                    )
                except TelegramError:
                    logging.error("Failed to send purchase notification to admin")
                
                # Show success message first, then redirect to channels
                success_message = MessageTemplates.order_confirmation(
                    channel_username,
                    purchase_data['members_count'],
                    purchase_data['points_cost']
                )
                success_message += "\n\n📢 الآن يمكنك الانضمام للقنوات المتاحة لجمع المزيد من النقاط:"
                
                # Get available channels for the user
                channels = self.db.get_available_channels_for_user(user_id)
                
                if channels:
                    await query.edit_message_text(success_message, reply_markup=channels_keyboard(channels))
                else:
                    await query.edit_message_text(
                        success_message + "\n\n📢 لا توجد قنوات متاحة للانضمام حالياً", 
                        reply_markup=back_keyboard()
                    )
            else:
                message = "❌ حدث خطأ في إنشاء الطلب"
                # Clear purchase data even on error
                context.user_data.pop('purchase_data', None)
                await query.edit_message_text(message, reply_markup=back_keyboard())
    
    async def _handle_back_to_main(self, query):
        """Handle back to main menu"""
        await query.edit_message_text(
            MESSAGES['welcome'],
            reply_markup=main_keyboard()
        )
    
    async def _handle_redeem_code_prompt(self, query, context):
        """Handle redeem code prompt"""
        await query.edit_message_text(
            "🎟️ أرسل الكود الذي تريد استخدامه:",
            reply_markup=back_keyboard()
        )
        
        context.user_data['awaiting_code'] = True
    
    async def _handle_special_content(self, query, user_id, context):
        """Handle special content display for channel leavers only"""
        try:
            # Get all active channels to check user status
            all_channels = self.db.get_active_channels()
            user_subscriptions = self.db.get_user_subscriptions(user_id)
            
            # Check if user is currently subscribed to any channels
            if user_subscriptions:
                # User is currently subscribed - check if they are still actual members
                if context:
                    await self._verify_user_subscriptions(context.bot, user_id)
                    # Re-check subscriptions after verification
                    user_subscriptions = self.db.get_user_subscriptions(user_id)
            
            # Only show content if user is not currently subscribed to any channels
            # OR if user is a known channel leaver
            is_leaver = self.db.is_channel_leaver(user_id)
            has_active_subscriptions = len(user_subscriptions) > 0
            
            if has_active_subscriptions and not is_leaver:
                # User is currently subscribed and not a known leaver - hide content
                message = "💬 المحتوى الخاص\n\n"
                message += "❌ المحتوى الخاص متاح فقط للمستخدمين غير المشتركين في القنوات\n\n"
                message += "إذا كنت تريد الوصول للمحتوى الخاص، يمكنك إلغاء الاشتراك من القنوات أولاً"
                await query.edit_message_text(message, reply_markup=back_keyboard())
                return
            
            # User can see special content - show it
            special_content = self.db.get_special_content()
            
            if not special_content:
                # No special content available - add some default content
                self.db.add_special_content(
                    "رسالة ترحيب خاصة",
                    "🎉 مرحباً بك في المحتوى الخاص!\n\n"
                    "هذا المحتوى متاح فقط للمستخدمين الذين لم يشتركوا في القنوات أو الذين غادروا القنوات.\n\n"
                    "💡 نصائح خاصة:\n"
                    "• يمكنك الحصول على نقاط إضافية من الأنشطة الخاصة\n"
                    "• إذا اشتركت في قناة ثم غادرتها، ستخسر 5 نقاط لكن ستعود لرؤية هذا المحتوى\n"
                    "• المحتوى الخاص يتم تحديثه بانتظام\n\n"
                    "📞 للمزيد من المعلومات، تواصل مع الإدارة"
                )
                special_content = self.db.get_special_content()
            
            message = "💬 المحتوى الخاص\n\n"
            message += "✅ يمكنك الوصول للمحتوى الخاص لأنك غير مشترك في القنوات\n\n"
            
            for content in special_content[:3]:  # Show first 3 items
                message += f"📝 **{content['content_title']}**\n"
                message += f"{content['content_message']}\n\n"
                message += "───────────────\n\n"
            
            if len(special_content) > 3:
                message += f"💡 يوجد {len(special_content) - 3} محتوى إضافي..."
            
            await query.edit_message_text(message, reply_markup=back_keyboard(), parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"Error handling special content: {e}")
            await query.edit_message_text(
                "❌ حدث خطأ في تحميل المحتوى الخاص",
                reply_markup=back_keyboard()
            )
    
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        if not update or not update.effective_user:
            return
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Handle verification for new users first
        if context.user_data.get('awaiting_verification'):
            await self._process_verification(update, context)
            return
        
        # Ensure user exists
        self.db.add_user(user_id, update.effective_user.username, update.effective_user.first_name)
        
        # Handle code redemption
        if context.user_data.get('awaiting_code'):
            context.user_data.pop('awaiting_code', None)
            
            result = self.db.redeem_code(user_id, text)
            if result is None:
                message = MESSAGES['invalid_code']
            elif result == -1:
                message = MESSAGES['code_already_used']
            else:
                message = MESSAGES['code_redeemed'].format(points=result)
            
            await update.message.reply_text(message, reply_markup=main_keyboard())
            return
        
        # Handle channel username for purchase
        if context.user_data.get('purchase_data', {}).get('awaiting_channel'):
            context.user_data['purchase_data']['awaiting_channel'] = False
            
            # Validate channel username
            if not is_valid_channel_username(text):
                await update.message.reply_text(
                    "❌ اسم القناة غير صحيح\nمثال صحيح: @mychannel",
                    reply_markup=back_keyboard()
                )
                return
            
            channel_username = text.replace('@', '')
            
            # Check if channel exists and get member count
            try:
                current_count = await get_channel_member_count(context.bot, channel_username)
                if current_count == 0:
                    await update.message.reply_text(
                        "❌ القناة غير موجودة أو لا يمكن الوصول إليها\nتأكد من أن البوت مدير في القناة",
                        reply_markup=back_keyboard()
                    )
                    return
            except Exception:
                await update.message.reply_text(
                    "❌ لا يمكن الوصول إلى القناة\nتأكد من أن البوت مدير في القناة",
                    reply_markup=back_keyboard()
                )
                return
            
            purchase_data = context.user_data['purchase_data']
            
            # Show confirmation
            message = (
                f"📝 تأكيد الطلب:\n\n"
                f"📢 القناة: @{channel_username}\n"
                f"👥 الأعضاء المطلوبين: {purchase_data['members_count']}\n"
                f"💰 التكلفة: {purchase_data['points_cost']} نقطة\n"
                f"📊 العدد الحالي: {current_count} عضو\n\n"
                f"هل أنت متأكد من المتابعة؟"
            )
            
            await update.message.reply_text(
                message,
                reply_markup=confirmation_keyboard("buy", channel_username)
            )
            return
        
        # Default response
        await update.message.reply_text(
            "استخدم الأزرار أدناه للتنقل في البوت 👇",
            reply_markup=main_keyboard()
        )

    async def _process_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process user verification response"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        expected_code = context.user_data.get('verification_code')
        attempts = context.user_data.get('verification_attempts', 0)
        
        # Check if the entered number matches
        try:
            entered_code = int(text)
            if entered_code == expected_code:
                # Verification successful
                context.user_data['verified'] = True
                context.user_data.pop('awaiting_verification', None)
                context.user_data.pop('verification_code', None)
                context.user_data.pop('verification_attempts', None)
                
                # Now proceed with normal /start flow
                referred_by = context.user_data.pop('referred_by', None)
                
                # Continue with user registration
                await self._complete_user_registration(update, context, referred_by)
                
            else:
                # Wrong code
                attempts += 1
                context.user_data['verification_attempts'] = attempts
                
                if attempts >= 3:
                    # Too many attempts, block user
                    await update.message.reply_text(
                        "❌ فشل التحقق بعد 3 محاولات\n\n"
                        "تم رفض دخولك للبوت لأسباب أمنية.\n"
                        "يمكنك المحاولة مرة أخرى لاحقاً بالضغط على /start"
                    )
                    # Clear all verification data
                    context.user_data.clear()
                else:
                    # Allow retry
                    remaining = 3 - attempts
                    await update.message.reply_text(
                        f"❌ الرقم خاطئ!\n\n"
                        f"يرجى كتابة الرقم **{expected_code}** بالضبط\n\n"
                        f"⚠️ المحاولات المتبقية: {remaining}",
                        parse_mode='Markdown'
                    )
        except ValueError:
            # Not a number
            attempts += 1
            context.user_data['verification_attempts'] = attempts
            
            if attempts >= 3:
                await update.message.reply_text(
                    "❌ فشل التحقق بعد 3 محاولات\n\n"
                    "تم رفض دخولك للبوت لأسباب أمنية.\n"
                    "يمكنك المحاولة مرة أخرى لاحقاً بالضغط على /start"
                )
                context.user_data.clear()
            else:
                remaining = 3 - attempts
                await update.message.reply_text(
                    f"❌ يجب كتابة الرقم فقط!\n\n"
                    f"الرقم المطلوب: **{expected_code}**\n\n"
                    f"⚠️ المحاولات المتبقية: {remaining}",
                    parse_mode='Markdown'
                )

    async def _complete_user_registration(self, update: Update, context: ContextTypes.DEFAULT_TYPE, referred_by=None):
        """Complete user registration after successful verification"""
        user = update.effective_user
        user_id = user.id
        
        # Add user to database  
        user_added = self.db.add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by=referred_by
        )
        
        # Award referral points if user was referred and is new
        if user_added and referred_by and referred_by != user.id:
            self.db.update_user_points(referred_by, REFERRAL_POINTS)
            
            # Notify referrer
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 تم قبول دعوتك!\nحصلت على {REFERRAL_POINTS} نقطة من دعوة @{user.username or user.first_name}"
                )
            except TelegramError:
                pass
        
        # Get bot username for referral links
        if not self.bot_username:
            bot_info = await context.bot.get_me()
            self.bot_username = bot_info.username
        
        # Check mandatory channels for all users (including returning ones)
        mandatory_channels = self.db.get_mandatory_channels()
        if mandatory_channels:
            from utils import check_mandatory_channels_membership
            all_subscribed, missing_channels = await check_mandatory_channels_membership(
                context.bot, user_id, mandatory_channels
            )
            
            if not all_subscribed:
                # Show mandatory channels message
                welcome_msg = "👋 أهلاً وسهلاً!\n\n🔒 للاستمرار، يجب الاشتراك في القنوات التالية:\n\n"
                for channel in missing_channels:
                    channel_link = f"https://t.me/{channel['channel_username']}"
                    welcome_msg += f"📢 @{channel['channel_username']}\n"
                    if channel.get('channel_title'):
                        welcome_msg += f"📝 {channel['channel_title']}\n"
                    welcome_msg += f"{channel_link}\n\n"
                welcome_msg += "✅ بعد الاشتراك، اضغط /start مرة أخرى"
                
                await update.message.reply_text(welcome_msg)
                return
        
        # Send admin notification ONLY for new users (not returning ones)
        if user_added:  # Only send notification for genuinely new users
            # Get total user count
            total_users = self.db.get_stats()['users']
            
            # Check if user is legitimate (has profile photo, first name, etc.)
            user_verification = await check_user_legitimacy(context.bot, user)
            
            # Send notification to admin
            try:
                admin_message = f"🆕 مستخدم جديد انضم للبوت!\n\n"
                admin_message += f"👤 الاسم: {user.first_name}\n"
                if user.username:
                    admin_message += f"📱 المعرف: @{user.username}\n"
                admin_message += f"🆔 ID: {user.id}\n"
                
                # Add verification status
                if user_verification['is_legitimate']:
                    admin_message += f"✅ المستخدم: حقيقي\n"
                else:
                    admin_message += f"⚠️ المستخدم: مشكوك فيه\n"
                    admin_message += f"📝 الأسباب: {', '.join(user_verification['warnings'])}\n"
                
                admin_message += f"🔐 اجتاز التحقق الأمني: ✅\n"
                
                if referred_by:
                    admin_message += f"👥 تم دعوته بواسطة: {referred_by}\n"
                admin_message += f"\n📊 إجمالي المستخدمين: {total_users}"
                
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_message
                )
            except TelegramError:
                logging.error("Failed to send user notification to admin")

        # Welcome message for new user
        welcome_text = "🎉 مرحباً بك في بوت تجميع النقاط!\n\n📊 يمكنك كسب النقاط من خلال:\n• الانضمام للقنوات\n• دعوة الأصدقاء\n• المكافآت اليومية\n\n🛒 استخدم النقاط لشراء أعضاء لقناتك"
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=main_keyboard()
        )
