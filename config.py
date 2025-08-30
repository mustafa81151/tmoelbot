import os

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', 'your_bot_token_here')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))  # Replace with actual admin Telegram ID

# Database Configuration
DATABASE_PATH = 'bot_database.db'

# Point System Configuration
DAILY_REWARD_POINTS = 4
REFERRAL_POINTS = 5
NORMAL_CHANNEL_POINTS = 3
VIP_CHANNEL_POINTS = 4

# Shop Configuration
SHOP_PRICES = {
    10: 20,   # 10 members = 20 points
    25: 50,   # 25 members = 50 points
    50: 100,  # 50 members = 100 points
    100: 200  # 100 members = 200 points
}

# Bot Messages in Arabic
MESSAGES = {
    'welcome': '🎉 أهلاً وسهلاً بك في بوت تجميع النقاط!\n\nاستخدم الأزرار أدناه للتنقل في البوت.',
    'account_info': '📊 معلومات حسابك:\n\n💰 النقاط: {points}\n👥 الإحالات: {referrals}\n📢 القنوات: {channels}',
    'daily_reward_claimed': '🎁 تم استلام هديتك اليومية!\nحصلت على {points} نقطة',
    'daily_reward_already_claimed': '⏰ لقد استلمت هديتك اليومية بالفعل!\nعد غداً لاستلام المزيد',
    'referral_link': '🔗 رابط الإحالة الخاص بك:\n{link}\n\nشارك هذا الرابط مع أصدقائك واحصل على {points} نقطة عن كل إحالة!',
    'insufficient_points': '❌ نقاطك غير كافية لهذا الشراء!\nتحتاج إلى {required} نقطة وعندك {current} نقطة',
    'order_created': '✅ تم إنشاء طلبك بنجاح!\n\nالقناة: @{channel}\nالأعضاء المطلوبين: {members}\nتم خصم {points} نقطة من رصيدك',
    'no_channels': '📢 لا توجد قنوات متاحة حالياً\nجرب مرة أخرى لاحقاً',
    'join_required': 'يجب عليك الانضمام إلى القناة @{channel} أولاً',
    'points_earned': '🎉 رائع! حصلت على {points} نقطة',
    'code_redeemed': '🎟️ تم استخدام الكود بنجاح!\nحصلت على {points} نقطة',
    'invalid_code': '❌ الكود غير صحيح أو منتهي الصلاحية',
    'code_already_used': '⚠️ لقد استخدمت هذا الكود من قبل'
}

# Admin Messages
ADMIN_MESSAGES = {
    'user_not_found': '❌ المستخدم غير موجود',
    'points_added': '✅ تم إضافة {points} نقطة للمستخدم {user_id}',
    'points_removed': '✅ تم خصم {points} نقطة من المستخدم {user_id}',
    'channel_added': '✅ تم إضافة القناة @{channel} من نوع {type}\nالهدف: {target} عضو',
    'channel_removed': '✅ تم حذف القناة @{channel}',
    'code_created': '🎟️ تم إنشاء الكود: {code}\nالنقاط: {points}\nالحد الأقصى: {limit}',
    'stats_message': '📊 إحصائيات البوت:\n\n👥 المستخدمين: {users}\n📢 القنوات: {channels}\n💰 النقاط الموزعة: {total_points}\n📦 الطلبات النشطة: {active_orders}'
}
