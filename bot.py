import os
import json
import logging
import asyncio
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
CATEGORY, AMOUNT, DESCRIPTION = range(3)

# Simple categories - no emojis to avoid encoding issues
CATEGORIES = [
    "Food",
    "Transport",
    "Rent",
    "Utilities",
    "Shopping",
    "Healthcare",
    "Entertainment",
    "Education",
    "Travel",
    "Income",
    "Other"
]

class ExpenseTracker:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.filename = f"expenses_{user_id}.json"
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
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            return {"total": 0, "count": 0}
        
        now = datetime.now()
        if period == "day":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = datetime.min
        
        total = 0
        count = 0
        for expense in self.expenses:
            try:
                exp_date = datetime.strptime(expense['date'], "%Y-%m-%d %H:%M:%S")
                if exp_date >= start_date:
                    total += expense['amount']
                    count += 1
            except:
                continue
        
        return {"total": total, "count": count}
    
    def get_recent(self, limit: int = 5) -> List[Dict]:
        """Get recent expenses"""
        return sorted(self.expenses, 
                     key=lambda x: x['date'], 
                     reverse=True)[:limit]

# ========== COMMAND HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome = """
    Expense Tracker Bot
    
    Commands:
    /add - Add expense
    /today - Today's total
    /week - Weekly total
    /month - Monthly total
    /recent - Recent expenses
    /help - Show help
    """
    await update.message.reply_text(welcome)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message"""
    help_text = """
    How to use:
    
    1. /add - Add expense
       - Select category
       - Enter amount
       - Add description
    
    2. View totals:
       - /today - Today
       - /week - This week
       - /month - This month
    
    3. /recent - See last 5 expenses
    
    Use 'Income' category for money received.
    """
    await update.message.reply_text(help_text)

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start add expense conversation"""
    keyboard = []
    for i in range(0, len(CATEGORIES), 3):
        row = []
        for j in range(3):
            if i + j < len(CATEGORIES):
                row.append(InlineKeyboardButton(
                    CATEGORIES[i + j], 
                    callback_data=f"cat_{CATEGORIES[i + j]}"
                ))
        keyboard.append(row)
    
    await update.message.reply_text(
        "Select a category:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CATEGORY

async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store category and ask for amount"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("cat_", "")
    context.user_data['category'] = category
    
    await query.edit_message_text(
        f"Category: {category}\n\n"
        "Enter amount (e.g., 15.50):"
    )
    return AMOUNT

async def amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store amount and ask for description"""
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
    except ValueError:
        await update.message.reply_text("Please enter a valid number:")
        return AMOUNT
    
    await update.message.reply_text(
        f"Amount: ${amount:.2f}\n\n"
        "Enter description (optional):"
    )
    return DESCRIPTION

async def description_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the expense"""
    description = update.message.text
    
    tracker = ExpenseTracker(update.effective_user.id)
    expense = tracker.add_expense(
        amount=context.user_data['amount'],
        category=context.user_data['category'],
        description=description
    )
    
    await update.message.reply_text(
        f"✅ Expense added!\n"
        f"ID: #{expense['id']}\n"
        f"Category: {expense['category']}\n"
        f"Amount: ${expense['amount']:.2f}"
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("Cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

async def show_summary(update: Update, period: str):
    """Show summary for period"""
    tracker = ExpenseTracker(update.effective_user.id)
    summary = tracker.get_summary(period)
    
    period_name = {
        "day": "Today",
        "week": "This week",
        "month": "This month"
    }.get(period, period)
    
    if summary['count'] == 0:
        await update.message.reply_text(f"No expenses for {period_name.lower()}.")
    else:
        await update.message.reply_text(
            f"{period_name}:\n"
            f"Total: ${summary['total']:.2f}\n"
            f"Transactions: {summary['count']}"
        )

async def today_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, "day")

async def week_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, "week")

async def month_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_summary(update, "month")

async def recent_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent expenses"""
    tracker = ExpenseTracker(update.effective_user.id)
    expenses = tracker.get_recent(5)
    
    if not expenses:
        await update.message.reply_text("No expenses yet.")
        return
    
    text = "Recent expenses:\n\n"
    for exp in expenses:
        text += f"#{exp['id']} - {exp['category']}: ${exp['amount']:.2f}\n"
        if exp['description']:
            text += f"  {exp['description']}\n"
        text += "\n"
    
    await update.message.reply_text(text)

# ========== MAIN FUNCTION ==========

def main():
    """Start the bot"""
    # Get token from environment
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        print("ERROR: BOT_TOKEN not set!")
        print("Please set BOT_TOKEN on Railway:")
        print("1. Go to Railway dashboard")
        print("2. Select your project")
        print("3. Click 'Variables'")
        print("4. Add BOT_TOKEN=your_token")
        return
    
    print("Starting Expense Tracker Bot...")
    
    # Create application with timeout settings
    application = Application.builder() \
        .token(TOKEN) \
        .read_timeout(30) \
        .write_timeout(30) \
        .connect_timeout(30) \
        .pool_timeout(30) \
        .build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_expense)],
        states={
            CATEGORY: [CallbackQueryHandler(category_chosen)],
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_received)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_received)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False  # Simplified
    )
    
    # Add command handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('today', today_summary))
    application.add_handler(CommandHandler('week', week_summary))
    application.add_handler(CommandHandler('month', month_summary))
    application.add_handler(CommandHandler('recent', recent_expenses))
    
    # Start bot with error handling
    print("Bot is running...")
    
    # Run with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            application.run_polling(
                drop_pending_updates=True,
                timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                print("Retrying in 10 seconds...")
                asyncio.run(asyncio.sleep(10))
            else:
                print("Max retries reached. Bot failed to start.")
                raise

if __name__ == '__main__':
    main()