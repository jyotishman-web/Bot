# 🤖 Perchance AI Character Generator Telegram Bot

A Telegram bot that generates AI character images from [perchance.org/ai-character-generator](https://perchance.org/ai-character-generator) using browser automation.

---

## 📁 File Structure

```
perchance-bot/
├── bot.py              # Main bot logic & Telegram handlers
├── browser.py          # Playwright browser automation
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── .env                # Your secrets (never commit this!)
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

---

## ⚙️ Setup Instructions

### 1. Clone your repo
```bash
git clone https://github.com/YOUR_USERNAME/perchance-bot.git
cd perchance-bot
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps          # Linux only
```

### 4. Set up your bot token
```bash
cp .env.example .env
```
Edit `.env` and add your Telegram bot token:
```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

### 5. Run the bot
```bash
python bot.py
```

---

## 🚀 How to Deploy on a VPS (keep it running 24/7)

### Using `screen` (simple)
```bash
screen -S perchance-bot
python bot.py
# Press Ctrl+A then D to detach
```

### Using `systemd` (recommended)
Create `/etc/systemd/system/perchance-bot.service`:
```ini
[Unit]
Description=Perchance Telegram Bot
After=network.target

[Service]
WorkingDirectory=/path/to/perchance-bot
ExecStart=/path/to/perchance-bot/venv/bin/python bot.py
Restart=always
EnvironmentFile=/path/to/perchance-bot/.env

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable perchance-bot
sudo systemctl start perchance-bot
sudo systemctl status perchance-bot
```

---

## 📝 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Usage instructions |
| Any text | Generate a character image |

---

## ⚠️ Notes

- 18+ content is enabled by default
- Requests are queued one at a time
- Generation takes ~10-20 seconds
- This bot uses browser automation — may break if perchance updates their site
