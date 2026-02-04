import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from http.server import BaseHTTPRequestHandler
import socketserver
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# ========== HEALTH CHECK SERVER ==========
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Disable logging

def start_health_server():
    """Start health check server on port 8080"""
    port = int(os.getenv('PORT', '8080'))
    with socketserver.TCPServer(("", port), HealthHandler) as httpd:
        print(f"✅ Health server running on port {port}")
        httpd.serve_forever()

# ========== BOT CODE ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
CATEGORY, AMOUNT, DESCRIPTION, CONFIRM = range(4)

# Categories
CATEGORIES = [
    ["🍔 Food", "🍕 Dining"],
    ["🚗 Transport", "⛽ Fuel"],
    ["🏠 Rent", "⚡ Utilities"],
    ["🛒 Shopping", "👕 Clothing"],
    ["🏥 Healthcare", "💊 Medicine"],
    ["🎉 Entertainment", "🎬 Movies"],
    ["📚 Education", "💻 Tech"],
    ["✈️ Travel", "🏨 Hotel"],
    ["💰 Income", "💼 Salary"],
    ["📊 Other", "🎁 Gifts"]
]

class ExpenseTracker:
    def __init__(self, user_id: int):
        self.user_id = user_id
        # Railway provides /data volume for persistence
        self.data_dir = "/data" if os.path.exists("/data") else "."
        os.makedirs(self.data_dir, exist_ok=True)
        self.filename = os.path.join(self.data_dir, f"expenses_{user_id}.json")
        self.expenses = self.load_expenses()
        logger.info(f"Loaded {len(self.expenses)} expenses for user {user_id}")
    
    def load_expenses(self) -> List[Dict]:
        """Load expenses from JSON file"""
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                logger.info(f"Loaded expenses from {self.filename}")
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info(f"No existing data for user {self.user_id}")
            return []
    
    def save_expenses(self):
        """Save expenses to JSON file"""
        with open(self.filename, 'w') as f:
            json.dump(self.expenses, f, indent=2)
        logger.info(f"Saved {len(self.expenses)} expenses to {self.filename}")
    
    def add_expense(self, amount: float, category: str, description: str = "") -> Dict:
        """Add a new expense"""
        expense = {
            "id": len(self.expenses) + 1,
            "date": datetime.now().isoformat(),
            "amount": float(amount),
            "category": category,
            "description": description
        }
        self.expenses.append(expense)
        self.save_expenses()
        logger.info(f"User {self.user_id} added expense: {category} ${amount}")
        return expense
    
    def get_summary(self, period: str = "month") -> Dict:
        """Get expense summary for a period"""
        if not self.expenses:
            return {"total": 0, "by_category": {}, "count": 0}
        
        now = datetime.now()
        if period == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == "year":
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = datetime.min
        
        filtered = []
        for expense in self.expenses:
            try:
                exp_date = datetime.fromisoformat(expense['date'].replace('Z', '+00:00'))
                if exp_date >= start_date:
                    filtered.append(expense)
            except:
                continue
        
        total = sum(exp['amount'] for exp in filtered)
        by_category = {}
        for exp in filtered:
            category = exp['category']
            by_category[category] = by_category.get(category, 0) + exp['amount']
        
        return {
            "total": total,
            "by_category": by_category,
            "count": len(filtered)
        }
    
    def get_recent_expenses(self, limit: int = 10) -> List[Dict]:
        """Get recent expenses"""
        try:
            sorted_expenses = sorted(self.expenses, 
                                   key=lambda x: x.get('date', ''), 
                                   reverse=True)
            return sorted_expenses[:limit]
        except:
            return []
    
    def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense by ID"""
        for i, expense in enumerate(self.expenses):
            if expense.get('id') == expense_id:
                del self.expenses[i]
                self.save_expenses()
                logger.info(f"User {self.user_id} deleted expense #{expense_id}")
                return True
        return False

# ========== COMMAND HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome = """
    💰 *Telegram Expenses Tracker*
    
    *Quick Commands:*
    /add - Record expense or income
    /today - Today's spending
    /week - Weekly summary
    /month - Monthly overview
    /recent - Recent transactions
    /delete <id> - Remove transaction
    /help - Detailed guide
    
    📊 Your data is saved automatically!
    """
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    help_text = """
    🤖 *Bot Guide*
    
    *1. Add Transaction*
    Use /add then:
    • Pick a category
    • Enter amount (like 15.50)
    • Add optional description
    
    *2. View Reports*
    • /today - Today's total
    • /week - Last 7 days
    • /month - Current month
    
    *3. Manage Data*
    • /recent - See last 10 entries
    • /delete 5 - Remove item #5
    
    💡 *Tip:* Use "💰 Income" for money received!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add expense conversation"""
    keyboard = []
    for row in CATEGORIES:
        keyboard_row = []
        for category in row:
            keyboard_row.append(
                InlineKeyboardButton(category, callback_data=f"cat_{category}")
            )
        keyboard.append(keyboard_row)
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    
    await update.message.reply_text(
        "📁 *Select Category:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store category and ask for amount"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END
    
    category = query.data.replace("cat_", "")
    context.user_data['category'] = category
    
    await query.edit_message_text(
        f"📁 *Category:* {category}\n\n"
        "💰 *Enter amount:*\n(Example: 15.50 or 100)",
        parse_mode='Markdown'
    )
    return AMOUNT

async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store amount and ask for description"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive.\n\nTry again:")
            return AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.\n\nExample: 15.50")
        return AMOUNT
    
    context.user_data['amount'] = amount
    
    await update.message.reply_text(
        f"💰 *Amount:* ${amount:.2f}\n\n"
        "📝 *Enter description (optional):*\n(Or type /skip)",
        parse_mode='Markdown'
    )
    return DESCRIPTION

async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store description and confirm"""
    description = update.message.text
    context.user_data['description'] = description
    
    category = context.user_data['category']
    amount = context.user_data['amount']
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Save", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")]
    ]
    
    await update.message.reply_text(
        f"📋 *Confirm Transaction*\n\n"
        f"• 🏷️ *Category:* {category}\n"
        f"• 💰 *Amount:* ${amount:.2f}\n"
        f"• 📝 *Description:* {description}\n\n"
        f"_Click Confirm to save_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CONFIRM

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip description"""
    context.user_data['description'] = "No description"
    
    category = context.user_data['category']
    amount = context.user_data['amount']
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Save", callback_data="confirm_yes")],
        [InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")]
    ]
    
    await update.message.reply_text(
        f"📋 *Confirm Transaction*\n\n"
        f"• 🏷️ *Category:* {category}\n"
        f"• 💰 *Amount:* ${amount:.2f}\n"
        f"• 📝 *Description:* No description\n\n"
        f"_Click Confirm to save_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CONFIRM

async def confirm_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm or cancel"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_yes":
        tracker = ExpenseTracker(query.from_user.id)
        expense = tracker.add_expense(
            amount=context.user_data['amount'],
            category=context.user_data['category'],
            description=context.user_data.get('description', '')
        )
        
        await query.edit_message_text(
            f"✅ *Transaction Saved!*\n\n"
            f"• 🆔 *ID:* #{expense['id']}\n"
            f"• 🏷️ *Category:* {expense['category']}\n"
            f"• 💰 *Amount:* ${expense['amount']:.2f}\n"
            f"• 📅 *Date:* {expense['date'][:10]}\n\n"
            f"_Use /recent to view all_",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ Transaction cancelled.")
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Operation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str):
    """Show summary for period"""
    tracker = ExpenseTracker(update.effective_user.id)
    summary = tracker.get_summary(period)
    
    period_names = {
        "day": "Today",
        "week": "This Week",
        "month": "This Month",
        "year": "This Year"
    }
    
    if summary['total'] == 0:
        await update.message.reply_text(
            f"📊 *{period_names[period]} Summary*\n\n"
            f"No transactions for {period_names[period].lower()} yet.\n\n"
            f"Use /add to record your first expense!",
            parse_mode='Markdown'
        )
        return
    
    text = f"📊 *{period_names[period]} Summary*\n\n"
    text += f"💰 **Total:** ${summary['total']:.2f}\n"
    text += f"📝 **Transactions:** {summary['count']}\n\n"
    
    if summary['by_category']:
        text += "*Breakdown by Category:*\n"
        # Sort by amount descending
        sorted_cats = sorted(summary['by_category'].items(), 
                           key=lambda x: x[1], 
                           reverse=True)
        for category, amount in sorted_cats:
            percentage = (amount / summary['total']) * 100
            text += f"• {category}: ${amount:.2f} ({percentage:.1f}%)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def today_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "day")

async def week_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "week")

async def month_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "month")

async def year_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "year")

async def recent_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent expenses"""
    tracker = ExpenseTracker(update.effective_user.id)
    expenses = tracker.get_recent_expenses(10)
    
    if not expenses:
        await update.message.reply_text(
            "📋 *Recent Transactions*\n\n"
            "No transactions yet!\n\n"
            "Use /add to record your first expense.",
            parse_mode='Markdown'
        )
        return
    
    text = "📋 *Recent Transactions*\n\n"
    for exp in expenses:
        try:
            date = datetime.fromisoformat(exp['date'].replace('Z', '+00:00'))
            date_str = date.strftime('%b %d')
        except:
            date_str = "Unknown date"
        
        text += (
            f"*#{exp.get('id', '?')}* - {date_str}\n"
            f"  {exp.get('category', 'Unknown')}: ${exp.get('amount', 0):.2f}\n"
            f"  {exp.get('description', 'No description')}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def delete_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete expense by ID"""
    if not context.args:
        await update.message.reply_text(
            "🗑️ *Delete Transaction*\n\n"
            "Usage: `/delete <ID>`\n"
            "Example: `/delete 5`\n\n"
            "Use `/recent` to see transaction IDs.",
            parse_mode='Markdown'
        )
        return
    
    try:
        expense_id = int(context.args[0])
        tracker = ExpenseTracker(update.effective_user.id)
        
        if tracker.delete_expense(expense_id):
            await update.message.reply_text(f"✅ Deleted transaction #{expense_id}")
        else:
            await update.message.reply_text(f"❌ Transaction #{expense_id} not found")
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid ID number")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status"""
    tracker = ExpenseTracker(update.effective_user.id)
    total_expenses = len(tracker.expenses)
    
    await update.message.reply_text(
        f"🤖 *Bot Status*\n\n"
        f"• ✅ Bot is running\n"
        f"• 📊 Your transactions: {total_expenses}\n"
        f"• 💾 Data location: {tracker.data_dir}\n"
        f"• 🕐 Server time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Send error to admin if available
    admin_id = os.getenv('ADMIN_ID')
    if admin_id:
        try:
            await context.bot.send_message(
                chat_id=int(admin_id),
                text=f"⚠️ Bot Error: {context.error}"
            )
        except:
            pass

# ========== MAIN FUNCTION ==========

def main():
    """Start the bot"""
    # Get token from Railway environment
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ ERROR: BOT_TOKEN environment variable not set!")
        logger.info("Please set BOT_TOKEN on Railway:")
        logger.info("1. Go to Railway dashboard")
        logger.info("2. Select your project")
        logger.info("3. Click 'Variables' tab")
        logger.info("4. Add BOT_TOKEN=your_token_here")
        return
    
    logger.info("🚀 Starting Telegram Expenses Tracker...")
    logger.info(f"📁 Data directory: {'/data' if os.path.exists('/data') else '.'}")
    
    # Start health server in background thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Create bot application
    application = Application.builder().token(TOKEN).build()
    
    # Add conversation handler for /add
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_expense)],
        states={
            CATEGORY: [CallbackQueryHandler(category_chosen)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)],
            DESCRIPTION: [
                CommandHandler('skip', skip_description),
                MessageHandler(filters.TEXT & ~filters.COMMAND, description_received)
            ],
            CONFIRM: [CallbackQueryHandler(confirm_expense)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add all command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('today', today_summary))
    application.add_handler(CommandHandler('week', week_summary))
    application.add_handler(CommandHandler('month', month_summary))
    application.add_handler(CommandHandler('year', year_summary))
    application.add_handler(CommandHandler('recent', recent_expenses))
    application.add_handler(CommandHandler('delete', delete_expense))
    application.add_handler(CommandHandler('status', status_command))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Set bot commands for Telegram menu
    async def post_init(app):
        await app.bot.set_my_commands([
            ('start', 'Start the bot'),
            ('add', 'Add new transaction'),
            ('today', "Today's summary"),
            ('week', 'Weekly summary'),
            ('month', 'Monthly summary'),
            ('recent', 'Recent transactions'),
            ('delete', 'Delete transaction'),
            ('help', 'Show help'),
            ('status', 'Bot status')
        ])
        logger.info("✅ Bot commands menu set")
    
    application.post_init = post_init
    
    # Start polling
    logger.info("🤖 Bot is now running...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()