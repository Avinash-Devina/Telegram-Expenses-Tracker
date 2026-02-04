python-3.11.0# 💰 Telegram Expenses Tracker

A personal expense tracking bot for Telegram, ready for one-click deployment on Railway.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new?template=https://github.com/yourusername/Telegram-Expenses-Tracker)

## 🚀 One-Click Deployment

1. **Click the "Deploy on Railway" button above**
2. **Add your BOT_TOKEN** (get from @BotFather on Telegram)
3. **That's it!** Your bot will be live in 1 minute

## 🤖 Bot Commands

- `/start` - Welcome message
- `/add` - Add expense/income
- `/today` - Today's summary
- `/week` - Weekly summary
- `/month` - Monthly summary
- `/recent` - Recent transactions
- `/delete <id>` - Delete transaction
- `/help` - Detailed guide
- `/status` - Bot status

## 📊 Features

- ✅ Expense & income tracking
- ✅ Daily/weekly/monthly reports
- ✅ 20+ categories with emojis
- ✅ Data persistence (Railway Volume)
- ✅ 24/7 uptime
- ✅ No database required

## 🛠️ Manual Setup

```bash
# Clone repository
git clone https://github.com/yourusername/Telegram-Expenses-Tracker.git
cd Telegram-Expenses-Tracker

# Install dependencies
pip install -r requirements.txt

# Run locally (set BOT_TOKEN in environment)
BOT_TOKEN=your_token_here python bot.py