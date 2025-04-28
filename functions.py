import sqlite3
from decimal import Decimal, ROUND_DOWN

# Database connection function
def get_db_connection():
    conn = sqlite3.connect("bot.db")
    conn.row_factory = sqlite3.Row
    return conn

def isExists(user_id):
    """Check if the user exists in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def insertUser(user_id, data):
    """Insert user data if user does not exist."""
    if not isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, balance, aff_by, affiliated, welcome_bonus, total_affs, affiliate_earnings, total_orders, total_spend)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, '0.0', data.get("aff_by", "none"), 0, 0, 0, '0.0', 0, '0.0'))
        conn.commit()
        conn.close()
        return True
    return False

def getData(user_id):
    """Retrieve all user data with precise Decimal handling."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        # Normalize to remove trailing zeros
        balance = Decimal(str(row["balance"])).normalize()
        affiliate_earnings = Decimal(str(row["affiliate_earnings"])).normalize()
        total_spend = Decimal(str(row["total_spend"])).normalize()
        return {
            "user_id": row["user_id"],
            "balance": balance,
            "aff_by": row["aff_by"],
            "affiliated": row["affiliated"],
            "welcome_bonus": row["welcome_bonus"],
            "total_affs": row["total_affs"],
            "affiliate_earnings": affiliate_earnings,
            "total_orders": row["total_orders"],
            "total_spend": total_spend
        }
    return None

def addBalance(user_id, amount):
    """Add balance to the user account with precise Decimal calculation."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        current_balance = Decimal(str(getData(user_id)["balance"]))
        amount = Decimal(str(amount))
        new_balance = (current_balance + amount).quantize(Decimal('0.00000000001'), rounding=ROUND_DOWN).normalize()
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (str(new_balance), user_id))
        conn.commit()
        conn.close()
        return True
    return False

def cutBalance(user_id, amount):
    """Deduct balance from the user account with precise Decimal calculation."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        current_balance = Decimal(str(getData(user_id)["balance"]))
        amount = Decimal(str(amount))
        if current_balance >= amount:
            new_balance = (current_balance - amount).quantize(Decimal('0.00000000001'), rounding=ROUND_DOWN).normalize()
            cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (str(new_balance), user_id))
            conn.commit()
            conn.close()
            return True
    return False

def setWelcomeStatus(user_id):
    """Set the welcome bonus status for the user."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET welcome_bonus = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

def setAffiliatedStatus(user_id):
    """Set the affiliate status for the user."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET affiliated = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

def addAffiliateCount(user_id):
    """Increment the affiliate count for the user."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET total_affs = total_affs + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

def addAffiliateEarning(user_id, amount):
    """Add affiliate earnings to the user with precise Decimal calculation."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        current_earnings = Decimal(str(getData(user_id)["affiliate_earnings"]))
        amount = Decimal(str(amount))
        new_earnings = (current_earnings + amount).quantize(Decimal('0.00000000001'), rounding=ROUND_DOWN).normalize()
        cursor.execute("UPDATE users SET affiliate_earnings = ? WHERE user_id = ?", (str(new_earnings), user_id))
        conn.commit()
        conn.close()
        return True
    return False

def update_order_stats(user_id, total_cost):
    """Update user's total_orders count and total_spend amount."""
    if isExists(user_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        current_data = getData(user_id)
        current_orders = current_data["total_orders"]
        current_spend = Decimal(str(current_data["total_spend"]))
        total_cost = Decimal(str(total_cost))
        
        new_orders = current_orders + 1
        new_spend = (current_spend + total_cost).quantize(Decimal('0.00000000001'), rounding=ROUND_DOWN).normalize()
        
        cursor.execute("UPDATE users SET total_orders = ?, total_spend = ? WHERE user_id = ?", 
                       (new_orders, str(new_spend), user_id))
        conn.commit()
        conn.close()
        return True
    return False

def get_total_users():
    """Return total number of users."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def save_order(user_id, order_data):
    """Save an order to the user's history, keeping only the last 5."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (order_id, user_id, service_name, timestamp, total_cost) VALUES (?, ?, ?, ?, ?)",
                   (order_data["order_id"], user_id, order_data["service_name"], order_data["timestamp"], str(order_data["total_cost"])))
    cursor.execute("DELETE FROM orders WHERE user_id = ? AND order_id NOT IN "
                   "(SELECT order_id FROM orders WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5)",
                   (user_id, user_id))
    conn.commit()
    conn.close()

def get_order_history(user_id):
    """Retrieve the user's order history, sorted by timestamp (newest first)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, service_name, timestamp FROM orders WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"order_id": row["order_id"], "service_name": row["service_name"], "timestamp": row["timestamp"]} for row in rows]