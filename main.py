#!/usr/bin/env python3
"""
Telegram Points Collection Bot with Marketplace and VIP System
Created for Arabic-speaking users with comprehensive admin features
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    filters
)
# Removed APScheduler import - using built-in asyncio

from database import Database
from bot_handlers import BotHandlers
from admin_handlers import AdminHandlers
from config import BOT_TOKEN, ADMIN_ID
from utils import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def error_handler(update: object, context) -> None:
    """Handle errors"""
    error_message = str(context.error)
    
    # Ignore harmless Telegram API errors
    if "Message is not modified" in error_message:
        return  # This is normal when users click buttons quickly
    
    logger.error(f"Exception while handling an update: {context.error}")
    
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ حدث خطأ غير متوقع، يرجى المحاولة مرة أخرى"
        )

async def post_init(application):
    """Post initialization tasks"""
    logger.info("Bot initialization completed")
    
    # Notify admin that bot started
    try:
        await application.bot.send_message(
            chat_id=ADMIN_ID,
            text="🤖 تم تشغيل البوت بنجاح!\n\n"
                 "✅ البوت جاهز لاستقبال المستخدمين\n"
                 "🔄 تم تفعيل النظام التلقائي لفحص المغادرين كل 40 ثانية\n"
                 "🛡️ تم تفعيل التحقق من العضوية عند عرض القنوات\n"
                 "🧠 تم تفعيل العد الذكي - البوت يحسب فقط الأعضاء من الطلبات\n"
                 "🔍 تم تفعيل فحص الحسابات المزيفة والبوتات\n"
                 "💰 خصم نقاط حتى السالب عند ترك القنوات"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")

def main():
    """Main function to run the bot"""
    
    # Initialize database
    logger.info("Initializing database...")
    db = Database('bot_database.db')
    
    # Initialize handlers
    bot_handlers = BotHandlers(db)
    admin_handlers = AdminHandlers(db)
    
    # Create application
    logger.info("Creating bot application...")
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Setup periodic channel verification using asyncio
    async def periodic_channel_check():
        """Periodically check all channels for leavers"""
        while True:
            try:
                await asyncio.sleep(40)  # Wait 40 seconds
                all_channels = db.get_active_channels()
                completed_channels = []
                completed_orders = []
                for channel in all_channels:
                    await bot_handlers._check_channel_leavers(application.bot, channel['username'])
                    # Update channel member count using smart bot-only counting
                    completed, order_owner_id = db.update_channel_members(channel['username'])
                    if completed:
                        completed_channels.append(channel['username'])
                        completed_orders.append((channel['username'], order_owner_id))
                
                # Notify admin and order owners of completed channels
                if completed_channels:
                    channels_text = '\n'.join([f"- @{ch}" for ch in completed_channels])
                    try:
                        # Notify admin
                        await application.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"🎉 تم إكمال القنوات التالية:\n\n{channels_text}\n\n✅ تم إزالتها من التجميع تلقائياً"
                        )
                        
                        # Notify each order owner
                        for channel_name, order_owner_id in completed_orders:
                            if order_owner_id and order_owner_id != ADMIN_ID:
                                try:
                                    await application.bot.send_message(
                                        chat_id=order_owner_id,
                                        text=f"🎉 تهانينا! تم إكمال طلبك!\n\n📢 القناة: @{channel_name}\n✅ تم الوصول للعدد المطلوب من الأعضاء\n\n🙏 شكراً لاستخدام خدماتنا"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to notify order owner {order_owner_id} for channel @{channel_name}: {e}")
                    except Exception as e:
                        logger.error(f"Failed to notify admin of completed channels: {e}")
                
                logger.info(f"Completed periodic check for {len(all_channels)} channels ({len(completed_channels)} completed)")
            except Exception as e:
                logger.error(f"Error in periodic channel check: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    # Start periodic task
    async def start_periodic_tasks(application):
        """Start the periodic channel checking task"""
        logger.info("Starting periodic channel verification...")
        asyncio.create_task(periodic_channel_check())
    
    # Add the periodic task to the post_init
    original_post_init = post_init
    async def enhanced_post_init(application):
        await original_post_init(application)
        await start_periodic_tasks(application)
    
    # Update the application with enhanced post_init
    application = Application.builder().token(BOT_TOKEN).post_init(enhanced_post_init).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", bot_handlers.start))
    
    # Admin commands
    application.add_handler(CommandHandler("admin", admin_handlers.admin_menu))
    application.add_handler(CommandHandler("addpoints", admin_handlers.add_points))
    application.add_handler(CommandHandler("removepoints", admin_handlers.remove_points))
    application.add_handler(CommandHandler("addchannel", admin_handlers.add_channel))
    application.add_handler(CommandHandler("removechannel", admin_handlers.remove_channel))
    application.add_handler(CommandHandler("makecode", admin_handlers.make_code))
    application.add_handler(CommandHandler("orders", admin_handlers.view_orders))
    application.add_handler(CommandHandler("stats", admin_handlers.view_stats))
    application.add_handler(CommandHandler("broadcast", admin_handlers.broadcast))
    application.add_handler(CommandHandler("ban", admin_handlers.ban_user))
    application.add_handler(CommandHandler("unban", admin_handlers.unban_user))
    application.add_handler(CommandHandler("addmandatory", admin_handlers.add_mandatory_channel))
    application.add_handler(CommandHandler("removemandatory", admin_handlers.remove_mandatory_channel))
    application.add_handler(CommandHandler("userinfo", admin_handlers.get_user_info))

    
    # Callback query handlers
    async def callback_router(update: Update, context):
        """Route callback queries to appropriate handler"""
        if update.callback_query and update.callback_query.data and update.callback_query.data.startswith(('admin_', 'confirm_admin')):
            await admin_handlers.handle_callback_query(update, context)
        else:
            await bot_handlers.handle_callback(update, context)
    
    application.add_handler(CallbackQueryHandler(callback_router))
    
    # Message handlers - admin first, then regular
    async def message_router(update: Update, context):
        """Route messages to appropriate handler"""
        if update.effective_user and update.effective_user.id == ADMIN_ID and context.user_data.get('awaiting_admin_action'):
            await admin_handlers.handle_admin_text(update, context)
        else:
            await bot_handlers.handle_message(update, context)
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting bot...")
    print("🤖 تم تشغيل البوت بنجاح!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("📊 البوت جاهز لاستقبال المستخدمين...")
    
    # Run the bot
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\n🛑 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n❌ خطأ خطير: {e}")
