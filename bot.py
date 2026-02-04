import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List
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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
CATEGORY, AMOUNT, DESCRIPTION, CONFIRM = range(4)

# Categories for expenses
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
        self.data_dir = "/data" if os.path.exists("/data") else "."
        os.makedirs(self.data_dir, exist_ok=True)
        self.filename = os.path.join(self.data_dir, f"expenses_{user_id}.json")
        self.expenses = self.load_expenses()
    
    def load_expenses(self) -> List[Dict]:
        """Load expenses from JSON file"""
        try:
            with open(self.filename, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_expenses(self):
        """Save expenses to JSON file"""
        with open(self.filename, 'w') as f:
            json.dump(self.expenses, f, indent=2)
    
    def add_expense(self, amount: float, category: str, description: str = "") -> Dict:
        """Add a new expense"""
        expense = {
            "id": len(self.expenses) + 1,
            "date": datetime.now().isoformat(),
            "amount": amount,
            "category": category,
            "description": description
        }
        self.expenses.append(expense)
        self.save_expenses()
        return expense
    
    def get_summary(self, period: str = "month") -> Dict:
        """Get expense summary for a period"""
        if not self.expenses:
            return {"total": 0, "by_category": {}, "count": 0}
        
        # Calculate date ranges
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
        
        # Filter expenses
        filtered = []
        for expense in self.expenses:
            exp_date = datetime.fromisoformat(expense['date'])
            if exp_date >= start_date:
                filtered.append(expense)
        
        # Calculate totals
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
        sorted_expenses = sorted(self.expenses, 
                               key=lambda x: x['date'], 
                               reverse=True)
        return sorted_expenses[:limit]
    
    def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense by ID"""
        for i, expense in enumerate(self.expenses):
            if expense['id'] == expense_id:
                del self.expenses[i]
                self.save_expenses()
                return True
        return False

# ============== COMMAND HANDLERS ==============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome = """
    💰 *Telegram-Expenses-Tracker*
    
    *Commands:*
    /add - Add expense/income
    /today - Today's summary
    /week - Weekly summary
    /month - Monthly summary
    /recent - Recent transactions
    /delete <id> - Delete transaction
    /help - Show help
    
    Data is stored in JSON files.
    """
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    help_text = """
    📚 *How to Use*
    
    1. */add* - Add transaction
       • Select category
       • Enter amount
       • Add description
    
    2. View summaries:
       • /today - Today
       • /week - This week
       • /month - This month
    
    3. Manage:
       • /recent - Last 10
       • /delete <id> - Remove
    
    Use 💰 Income category for money received!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ============== ADD EXPENSE FLOW ==============

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
        "📂 Select a category:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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
        f"📁 Category: {category}\n\n"
        "💰 Enter amount (e.g., 15.50):"
    )
    return AMOUNT

async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store amount and ask for description"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive. Try again:")
            return AMOUNT
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number (e.g., 15.50):")
        return AMOUNT
    
    context.user_data['amount'] = amount
    
    await update.message.reply_text(
        f"💰 Amount: ${amount:.2f}\n\n"
        "📝 Enter description (or /skip):"
    )
    return DESCRIPTION

async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store description and confirm"""
    description = update.message.text
    context.user_data['description'] = description
    
    # Show confirmation
    category = context.user_data['category']
    amount = context.user_data['amount']
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Add", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")
        ]
    ]
    
    await update.message.reply_text(
        f"📋 *Confirm Transaction*\n\n"
        f"• Category: {category}\n"
        f"• Amount: ${amount:.2f}\n"
        f"• Description: {description}",
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
        [
            InlineKeyboardButton("✅ Add", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="confirm_no")
        ]
    ]
    
    await update.message.reply_text(
        f"📋 *Confirm Transaction*\n\n"
        f"• Category: {category}\n"
        f"• Amount: ${amount:.2f}\n"
        f"• Description: No description",
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
            f"✅ *Added Successfully!*\n\n"
            f"• ID: #{expense['id']}\n"
            f"• Category: {expense['category']}\n"
            f"• Amount: ${expense['amount']:.2f}\n"
            f"• Date: {expense['date'][:10]}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ Cancelled.")
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Operation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

# ============== SUMMARY COMMANDS ==============

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, period: str):
    """Show summary for period"""
    tracker = ExpenseTracker(update.effective_user.id)
    summary = tracker.get_summary(period)
    
    if summary['total'] == 0:
        await update.message.reply_text(f"No transactions for this {period}.")
        return
    
    # Format period name
    period_names = {
        "day": "Today",
        "week": "This Week",
        "month": "This Month",
        "year": "This Year"
    }
    
    text = f"📊 *{period_names[period]} Summary*\n\n"
    text += f"💰 Total: ${summary['total']:.2f}\n"
    text += f"📝 Transactions: {summary['count']}\n\n"
    
    if summary['by_category']:
        text += "*By Category:*\n"
        for category, amount in sorted(summary['by_category'].items(), 
                                      key=lambda x: x[1], reverse=True):
            text += f"• {category}: ${amount:.2f}\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def today_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "day")

async def week_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "week")

async def month_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "month")

async def year_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, context, "year")

# ============== OTHER COMMANDS ==============

async def recent_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent expenses"""
    tracker = ExpenseTracker(update.effective_user.id)
    expenses = tracker.get_recent_expenses(10)
    
    if not expenses:
        await update.message.reply_text("No transactions yet.")
        return
    
    text = "📋 *Recent Transactions*\n\n"
    for exp in expenses:
        date = datetime.fromisoformat(exp['date'])
        text += (
            f"*#{exp['id']}* - {date.strftime('%b %d')}\n"
            f"  {exp['category']}: ${exp['amount']:.2f}\n"
            f"  {exp['description']}\n\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def delete_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete expense by ID"""
    if not context.args:
        await update.message.reply_text(
            "Usage: /delete <id>\n"
            "Example: /delete 5\n"
            "Use /recent to see IDs"
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

# ============== MAIN FUNCTION ==============

def main():
    """Start the bot"""
    # Get token from environment (Railway will set this)
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        logger.error("❌ BOT_TOKEN not found!")
        logger.info("Set BOT_TOKEN in Railway environment variables")
        return
    
    logger.info("🚀 Starting Telegram-Expenses-Tracker...")
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add expense conversation
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
    
    # Add command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('today', today_summary))
    application.add_handler(CommandHandler('week', week_summary))
    application.add_handler(CommandHandler('month', month_summary))
    application.add_handler(CommandHandler('year', year_summary))
    application.add_handler(CommandHandler('recent', recent_expenses))
    application.add_handler(CommandHandler('delete', delete_expense))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🤖 Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()