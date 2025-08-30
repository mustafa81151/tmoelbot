import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import threading

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.local = threading.local()
        self.init_database()
    
    def get_connection(self):
        if not hasattr(self.local, 'connection'):
            self.local.connection = sqlite3.connect(self.db_path)
            self.local.connection.row_factory = sqlite3.Row
        return self.local.connection
    
    def init_database(self):
        """Initialize database with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                points INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                channels_joined INTEGER DEFAULT 0,
                last_daily_reward TEXT,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Channels table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('normal', 'vip', 'order')),
                target INTEGER NOT NULL,
                gained INTEGER DEFAULT 0,
                initial_count INTEGER DEFAULT 0,
                current_count INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                order_id INTEGER,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        ''')
        
        # Add missing columns for existing databases
        try:
            cursor.execute('ALTER TABLE channels ADD COLUMN initial_count INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute('ALTER TABLE channels ADD COLUMN current_count INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Add ban system to users table
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN banned_reason TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN banned_at TEXT')
        except sqlite3.OperationalError:
            pass
        
        # Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_username TEXT NOT NULL,
                members_count INTEGER NOT NULL,
                points_cost INTEGER NOT NULL,
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Redemption codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                points INTEGER NOT NULL,
                usage_limit INTEGER NOT NULL,
                used_count INTEGER DEFAULT 0,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Code usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS code_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (code_id) REFERENCES codes (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (code_id, user_id)
            )
        ''')
        
        # User channel subscriptions tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_channel_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                channel_username TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE (user_id, channel_username)
            )
        ''')
        
        # Banned users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                banned_by INTEGER NOT NULL,
                ban_reason TEXT DEFAULT 'Manual ban',
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (banned_by) REFERENCES users (id)
            )
        ''')
        
        # Create mandatory channels table
        cursor.execute('''CREATE TABLE IF NOT EXISTS mandatory_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT UNIQUE NOT NULL,
            channel_title TEXT,
            channel_link TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        )''')

        # Create channel leavers table to track users who left or never subscribed
        cursor.execute('''CREATE TABLE IF NOT EXISTS channel_leavers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_username TEXT NOT NULL,
            left_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            previously_subscribed BOOLEAN DEFAULT 0,
            penalty_applied BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE (user_id, channel_username)
        )''')

        # Create special content table for leavers
        cursor.execute('''CREATE TABLE IF NOT EXISTS special_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_title TEXT NOT NULL,
            content_message TEXT NOT NULL,
            target_channel TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_id ON users (id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channels_active ON channels (active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_leavers_user ON channel_leavers (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_leavers_channel ON channel_leavers (channel_username)')
        
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, referred_by: int = None):
        """Add a new user to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO users (id, username, first_name, referred_by) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, referred_by))
            
            if cursor.rowcount > 0 and referred_by:
                # Increment referral count for the referrer
                cursor.execute('UPDATE users SET referrals = referrals + 1 WHERE id = ?', (referred_by,))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error adding user: {e}")
            return False
    
    def update_user_username(self, user_id: int, username: str):
        """Update user's username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'UPDATE users SET username = ? WHERE id = ?',
                (username, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error updating user username: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def update_user_points(self, user_id: int, points: int):
        """Update user points (can be positive or negative)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET points = points + ? WHERE id = ?', (points, user_id))
        conn.commit()
        return cursor.rowcount > 0
    
    def set_user_points(self, user_id: int, points: int):
        """Set user points to a specific value"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET points = ? WHERE id = ?', (points, user_id))
        conn.commit()
        return cursor.rowcount > 0
    
    def can_claim_daily_reward(self, user_id: int) -> bool:
        """Check if user can claim daily reward"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_daily_reward FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            return True
        
        last_reward = datetime.fromisoformat(result[0])
        return datetime.now() - last_reward >= timedelta(days=1)
    
    def claim_daily_reward(self, user_id: int, points: int) -> bool:
        """Claim daily reward"""
        if not self.can_claim_daily_reward(user_id):
            return False
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        cursor.execute('''
            UPDATE users 
            SET points = points + ?, last_daily_reward = ? 
            WHERE id = ?
        ''', (points, now, user_id))
        
        conn.commit()
        return cursor.rowcount > 0
    
    def add_channel(self, username: str, channel_type: str, target: int, order_id: int = None, initial_count: int = 0) -> bool:
        """Add a new channel or reactivate existing one - intelligent bot counting only"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First check if channel exists
            cursor.execute('SELECT id, active FROM channels WHERE username = ?', (username.replace('@', ''),))
            existing = cursor.fetchone()
            
            if existing:
                # Channel exists - reactivate it with new settings
                # Clear all existing subscriptions for fresh start
                cursor.execute('''
                    DELETE FROM user_channel_subscriptions 
                    WHERE channel_username = ?
                ''', (username.replace('@', ''),))
                
                cursor.execute('''
                    UPDATE channels 
                    SET active = 1, type = ?, target = ?, gained = 0, current_count = 0, order_id = ?
                    WHERE username = ?
                ''', (channel_type, target, order_id, username.replace('@', '')))
                logging.info(f"✅ Reactivated existing channel @{username} with target {target} - cleared old subscriptions")
                conn.commit()
                return True
            else:
                # New channel - insert it
                cursor.execute('''
                    INSERT INTO channels (username, type, target, order_id, initial_count, current_count, gained, active) 
                    VALUES (?, ?, ?, ?, 0, 0, 0, 1)
                ''', (username.replace('@', ''), channel_type, target, order_id))
                logging.info(f"✅ Added new channel @{username} with target {target}")
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Error adding/updating channel: {e}")
            return False
    
    def remove_channel(self, username: str) -> bool:
        """Remove a channel"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM channels WHERE username = ?', (username.replace('@', ''),))
        conn.commit()
        return cursor.rowcount > 0
    
    def get_active_channels(self, channel_type: str = None) -> List[Dict]:
        """Get all active channels"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if channel_type:
            cursor.execute('SELECT * FROM channels WHERE active = 1 AND type = ?', (channel_type,))
        else:
            cursor.execute('SELECT * FROM channels WHERE active = 1')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_channel_members(self, username: str, current_count: int = 0):
        """Update channel member count based ONLY on bot subscriptions - intelligent counting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get channel info 
        cursor.execute('''
            SELECT id, target, order_id 
            FROM channels 
            WHERE username = ? AND active = 1
        ''', (username.replace('@', ''),))
        
        channel_info = cursor.fetchone()
        if not channel_info:
            return False, None
        
        channel_id, target, order_id = channel_info
        
        # SMART COUNTING: Only count verified real users who went through proper bot workflow
        # Get number of users who joined this channel via the bot AND are still subscribed
        # Get order owner to exclude them from the count
        order_owner_id = 8117492678  # Default admin as owner
        if order_id:
            cursor.execute('SELECT user_id FROM orders WHERE id = ?', (order_id,))
            owner_result = cursor.fetchone()
            if owner_result:
                order_owner_id = owner_result[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM user_channel_subscriptions ucs
            INNER JOIN users u ON ucs.user_id = u.id
            WHERE ucs.channel_username = ? 
            AND u.id != ?
        ''', (username.replace('@', ''), order_owner_id))
        
        gained_members = cursor.fetchone()[0]
        
        # Log the count for debugging
        logging.info(f"📊 Channel @{username}: {gained_members} verified real members from bot purchases")
        
        # Update gained members (this is the TRUE count from bot purchases)
        cursor.execute('''
            UPDATE channels 
            SET gained = ?, current_count = ? 
            WHERE id = ?
        ''', (gained_members, gained_members, channel_id))
        
        # Check if target reached
        if gained_members >= target:
            # Deactivate channel and complete order if exists
            cursor.execute('UPDATE channels SET active = 0 WHERE id = ?', (channel_id,))
            
            order_owner_id = None
            if order_id:  # order_id exists
                # Get order owner information
                cursor.execute('''
                    SELECT user_id FROM orders WHERE id = ?
                ''', (order_id,))
                order_result = cursor.fetchone()
                if order_result:
                    order_owner_id = order_result[0]
                
                cursor.execute('''
                    UPDATE orders 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (order_id,))
            
            conn.commit()
            return True, order_owner_id
        
        conn.commit()
        return False, None
    
    def get_available_channels_for_user(self, user_id: int) -> List[Dict]:
        """Get active channels (user eligibility will be checked in real-time)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all active channels - we'll check membership in real-time in the bot
        cursor.execute('''
            SELECT c.* FROM channels c
            WHERE c.active = 1 
            AND c.type IN ('normal', 'vip')
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_channel_subscribers(self, channel_username: str) -> List[int]:
        """Get list of users who joined this channel"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id FROM user_channel_subscriptions 
            WHERE channel_username = ?
        ''', (channel_username.replace('@', ''),))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_user_subscriptions(self, user_id: int) -> List[str]:
        """Get list of channels this user is subscribed to"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT channel_username FROM user_channel_subscriptions 
            WHERE user_id = ?
        ''', (user_id,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def user_joined_channel(self, user_id: int, channel_username: str, points: int) -> bool:
        """Record that user joined a channel and award points"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Record the subscription
            cursor.execute('''
                INSERT OR IGNORE INTO user_channel_subscriptions (user_id, channel_username) 
                VALUES (?, ?)
            ''', (user_id, channel_username.replace('@', '')))
            
            if cursor.rowcount > 0:  # New subscription
                # Award points and increment channels_joined count
                cursor.execute('''
                    UPDATE users 
                    SET points = points + ?, channels_joined = channels_joined + 1 
                    WHERE id = ?
                ''', (points, user_id))
                
                # Remove user from channel leavers if they were there
                self.remove_channel_leaver(user_id, channel_username)
                
                conn.commit()
                return True
            
            return False  # Already joined
        except Exception as e:
            logging.error(f"Error recording channel join: {e}")
            return False
    
    def ban_user(self, user_id: int, reason: str = "Admin ban") -> bool:
        """Ban a user from using the bot"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET is_banned = 1, banned_reason = ?, banned_at = ?
                WHERE id = ?
            ''', (reason, datetime.now().isoformat(), user_id))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error banning user {user_id}: {e}")
            return False
    
    def unban_user(self, user_id: int) -> bool:
        """Unban a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users 
                SET is_banned = 0, banned_reason = NULL, banned_at = NULL
                WHERE id = ?
            ''', (user_id,))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error unbanning user {user_id}: {e}")
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user information by username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM users WHERE username = ?
            ''', (username,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logging.error(f"Error getting user by username {username}: {e}")
            return None
    
    def get_ban_info(self, user_id: int) -> Optional[Dict]:
        """Get ban information for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT banned_reason, banned_at FROM users 
                WHERE id = ? AND is_banned = 1
            ''', (user_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
        except Exception as e:
            logging.error(f"Error getting ban info for user {user_id}: {e}")
            return None
    
    def is_user_banned(self, user_id: int) -> bool:
        """Check if user is banned"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT is_banned FROM users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        
        return bool(result and result[0])
    
    def penalize_channel_leaver(self, user_id: int, channel_username: str, penalty_points: int):
        """Penalize user for leaving a channel or clean up stale records"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if user was previously subscribed
            cursor.execute('''
                SELECT 1 FROM user_channel_subscriptions 
                WHERE user_id = ? AND channel_username = ?
            ''', (user_id, channel_username.replace('@', '')))
            was_subscribed = cursor.fetchone() is not None
            
            # Remove subscription record
            cursor.execute('''
                DELETE FROM user_channel_subscriptions 
                WHERE user_id = ? AND channel_username = ?
            ''', (user_id, channel_username.replace('@', '')))
            
            if cursor.rowcount > 0:  # User was subscribed
                if penalty_points > 0:
                    # Penalize user by removing points (allow negative balance) and decrementing channels count
                    cursor.execute('''
                        UPDATE users 
                        SET points = points - ?, 
                        channels_joined = channels_joined - 1 
                        WHERE id = ?
                    ''', (penalty_points, user_id))
                    logging.info(f"Penalized user {user_id} for leaving channel @{channel_username} (-{penalty_points} points)")
                else:
                    # Just clean up the record without penalty (for users who returned externally)
                    cursor.execute('''
                        UPDATE users 
                        SET channels_joined = channels_joined - 1 
                        WHERE id = ?
                    ''', (user_id,))
                    logging.info(f"Cleaned up stale record for user {user_id} in channel @{channel_username}")
                
                # Add user to channel leavers table
                cursor.execute('''
                    INSERT OR REPLACE INTO channel_leavers 
                    (user_id, channel_username, previously_subscribed, penalty_applied) 
                    VALUES (?, ?, ?, ?)
                ''', (user_id, channel_username.replace('@', ''), was_subscribed, penalty_points > 0))
                
                conn.commit()
        
        except Exception as e:
            logging.error(f"Error penalizing channel leaver: {e}")
    
    def add_channel_leaver(self, user_id: int, channel_username: str, previously_subscribed: bool = False):
        """Add user to channel leavers list (for users who never subscribed)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO channel_leavers 
                (user_id, channel_username, previously_subscribed, penalty_applied) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, channel_username.replace('@', ''), previously_subscribed, False))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error adding channel leaver: {e}")
            return False
    
    def is_channel_leaver(self, user_id: int, channel_username: str = None) -> bool:
        """Check if user is a channel leaver (left or never subscribed)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if channel_username:
                cursor.execute('''
                    SELECT 1 FROM channel_leavers 
                    WHERE user_id = ? AND channel_username = ?
                ''', (user_id, channel_username.replace('@', '')))
            else:
                cursor.execute('''
                    SELECT 1 FROM channel_leavers 
                    WHERE user_id = ?
                ''', (user_id,))
            
            return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"Error checking channel leaver status: {e}")
            return False
    
    def remove_channel_leaver(self, user_id: int, channel_username: str):
        """Remove user from channel leavers (when they resubscribe)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM channel_leavers 
                WHERE user_id = ? AND channel_username = ?
            ''', (user_id, channel_username.replace('@', '')))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error removing channel leaver: {e}")
            return False
    
    def add_special_content(self, title: str, message: str, target_channel: str = None) -> bool:
        """Add special content for channel leavers"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO special_content (content_title, content_message, target_channel) 
                VALUES (?, ?, ?)
            ''', (title, message, target_channel.replace('@', '') if target_channel else None))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Error adding special content: {e}")
            return False
    
    def get_special_content(self, target_channel: str = None) -> List[Dict]:
        """Get special content for channel leavers"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if target_channel:
                cursor.execute('''
                    SELECT * FROM special_content 
                    WHERE is_active = 1 AND (target_channel = ? OR target_channel IS NULL)
                    ORDER BY created_at DESC
                ''', (target_channel.replace('@', ''),))
            else:
                cursor.execute('''
                    SELECT * FROM special_content 
                    WHERE is_active = 1 
                    ORDER BY created_at DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Error getting special content: {e}")
            return []
    
    def create_order(self, user_id: int, channel_username: str, members_count: int, points_cost: int, initial_count: int = 0) -> int:
        """Create a new order and deduct points"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Deduct points from user
            cursor.execute('UPDATE users SET points = points - ? WHERE id = ?', (points_cost, user_id))
            
            # Create order
            cursor.execute('''
                INSERT INTO orders (user_id, channel_username, members_count, points_cost) 
                VALUES (?, ?, ?, ?)
            ''', (user_id, channel_username.replace('@', ''), members_count, points_cost))
            
            order_id = cursor.lastrowid
            
            # Add channel to channels table
            self.add_channel(
                username=channel_username,
                channel_type='normal',
                target=members_count,
                order_id=order_id,
                initial_count=initial_count
            )
            
            conn.commit()
            return order_id
        
        except Exception as e:
            logging.error(f"Error creating order: {e}")
            return 0
    
    def get_orders(self, status: str = None, user_id: int = None) -> List[Dict]:
        """Get orders with optional filtering"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT o.*, u.username, u.first_name 
            FROM orders o 
            LEFT JOIN users u ON o.user_id = u.id
        '''
        params = []
        conditions = []
        
        if status:
            conditions.append('o.status = ?')
            params.append(status)
        
        if user_id:
            conditions.append('o.user_id = ?')
            params.append(user_id)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY o.created_at DESC'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_order_info(self, order_id: int) -> Optional[Dict]:
        """Get order information with user details"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT o.*, u.username, u.first_name, u.id as owner_id
            FROM orders o 
            LEFT JOIN users u ON o.user_id = u.id
            WHERE o.id = ?
        ''', (order_id,))
        
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def create_code(self, code: str, points: int, usage_limit: int) -> bool:
        """Create a new redemption code"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO codes (code, points, usage_limit) 
                VALUES (?, ?, ?)
            ''', (code, points, usage_limit))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def redeem_code(self, user_id: int, code: str) -> Optional[int]:
        """Redeem a code and return points awarded"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get code info
            cursor.execute('''
                SELECT id, points, usage_limit, used_count 
                FROM codes 
                WHERE code = ? AND active = 1
            ''', (code,))
            
            code_info = cursor.fetchone()
            if not code_info:
                return None  # Invalid code
            
            code_id, points, usage_limit, used_count = code_info
            
            if used_count >= usage_limit:
                return None  # Code limit reached
            
            # Check if user already used this code
            cursor.execute('''
                SELECT id FROM code_usage 
                WHERE code_id = ? AND user_id = ?
            ''', (code_id, user_id))
            
            if cursor.fetchone():
                return -1  # Already used by this user
            
            # Record usage and award points
            cursor.execute('''
                INSERT INTO code_usage (code_id, user_id) 
                VALUES (?, ?)
            ''', (code_id, user_id))
            
            cursor.execute('UPDATE codes SET used_count = used_count + 1 WHERE id = ?', (code_id,))
            cursor.execute('UPDATE users SET points = points + ? WHERE id = ?', (points, user_id))
            
            conn.commit()
            return points
        
        except Exception as e:
            logging.error(f"Error redeeming code: {e}")
            return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get bot statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total users
        cursor.execute('SELECT COUNT(*) FROM users')
        stats['users'] = cursor.fetchone()[0]
        
        # Active channels
        cursor.execute('SELECT COUNT(*) FROM channels WHERE active = 1')
        stats['channels'] = cursor.fetchone()[0]
        
        # Total points distributed
        cursor.execute('SELECT SUM(points) FROM users')
        stats['total_points'] = cursor.fetchone()[0] or 0
        
        # Active orders
        cursor.execute('SELECT COUNT(*) FROM orders WHERE status = "active"')
        stats['active_orders'] = cursor.fetchone()[0]
        
        return stats
    
    def get_all_users(self) -> List[int]:
        """Get all user IDs for broadcasting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT id FROM users')
        return [row[0] for row in cursor.fetchall()]

    def get_user_by_username(self, username: str) -> Dict:
        """Get user information by username"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Remove @ if present
        username = username.replace('@', '')
        cursor.execute('SELECT * FROM users WHERE username = ? COLLATE NOCASE', (username,))
        result = cursor.fetchone()
        return dict(result) if result else None
    
    # Mandatory channels management
    def add_mandatory_channel(self, channel_username: str, channel_title: str = None, channel_link: str = None):
        """Add a mandatory channel"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO mandatory_channels (channel_username, channel_title, channel_link)
                VALUES (?, ?, ?)
            ''', (channel_username.replace('@', ''), channel_title, channel_link))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error adding mandatory channel: {e}")
            return False
    
    def remove_mandatory_channel(self, channel_username: str):
        """Remove a mandatory channel"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM mandatory_channels WHERE channel_username = ?', 
                         (channel_username.replace('@', ''),))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"Error removing mandatory channel: {e}")
            return False
    
    def get_mandatory_channels(self):
        """Get all active mandatory channels"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM mandatory_channels WHERE active = 1 ORDER BY added_at')
        results = cursor.fetchall()
        return [dict(row) for row in results]
    
    def check_user_mandatory_subscriptions(self, user_id: int):
        """Check which mandatory channels user is not subscribed to"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT mc.channel_username, mc.channel_title, mc.channel_link
            FROM mandatory_channels mc
            LEFT JOIN user_channel_subscriptions ucs ON mc.channel_username = ucs.channel_username AND ucs.user_id = ?
            WHERE mc.active = 1 AND ucs.id IS NULL
        ''', (user_id,))
        results = cursor.fetchall()
        return [dict(row) for row in results]
