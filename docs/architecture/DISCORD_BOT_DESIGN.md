# Discord Trading Bot - Design Document

## Overview
A Discord bot that allows users to query trading data and run analysis skills through natural language commands in Discord channels.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Discord Server                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  #trading-analysis                                       │   │
│  │  ├── User: "@Bot bias for NQ tomorrow"                   │   │
│  │  └── Bot: [Chart + Analysis Response]                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Discord API
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Trading Bot (Python)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Discord.py   │→ │ Command      │→ │ Script Executor       │ │
│  │ Listener     │  │ Parser (LLM) │  │ (subprocess)          │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
│                                              │                  │
│                                              ▼                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Available Skills & Scripts                               │   │
│  │ • retrieve_ict_context.py (Daily Bias)                   │   │
│  │ • retrieve_daily_stats.py (Statistical Analysis)         │   │
│  │ • generate_ict_chart.py (Chart Generation)               │   │
│  │ • analyze_weekly_profile.py (Weekly Context)             │   │
│  │ • fetch_economic_events.py (Calendar)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Setup Steps

### 1. Create Discord Bot Application
1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name it (e.g., "Trading Analyst")
3. Go to "Bot" tab → Click "Add Bot"
4. Copy the **Bot Token** (keep this secret!)
5. Enable these Intents:
   - ✅ Message Content Intent
   - ✅ Server Members Intent (optional)

### 2. Invite Bot to Your Server
1. Go to "OAuth2" → "URL Generator"
2. Select scopes: `bot`, `applications.commands`
3. Select permissions: `Send Messages`, `Attach Files`, `Read Message History`
4. Copy the generated URL → Open in browser → Select your server

### 3. Store Bot Token
Create or update `secrets.json` in project root:
```json
{
  "discord_bot_token": "YOUR_BOT_TOKEN_HERE",
  "openai_api_key": "sk-..." 
}
```

### 4. Install Dependencies
```bash
pip install discord.py openai
```

## Implementation

### Bot Script Location
`scripts/bot/discord_bot.py`

### Core Code Structure
```python
import discord
from discord.ext import commands
import subprocess
import os

# Load token from secrets.json
import json
with open('secrets.json') as f:
    secrets = json.load(f)

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')

@bot.command(name='bias')
async def daily_bias(ctx, ticker: str = 'NQ1'):
    """Get daily bias analysis for a ticker"""
    await ctx.send(f"🔄 Analyzing {ticker}...")
    
    # Run the analysis script
    result = subprocess.run(
        ['python', 'scripts/trader/retrieve_ict_context.py', ticker, '--next-day'],
        capture_output=True, text=True, cwd='c:/Users/vinay/tvDownloadOHLC'
    )
    
    # Generate chart
    subprocess.run(
        ['python', 'scripts/analysis/generate_ict_chart.py', ticker],
        cwd='c:/Users/vinay/tvDownloadOHLC'
    )
    
    # Send chart
    chart_path = f'c:/Users/vinay/tvDownloadOHLC/data/analysis/charts/{ticker}_ict_context_*.png'
    await ctx.send(file=discord.File(chart_path))

@bot.command(name='stats')
async def daily_stats(ctx, ticker: str, prev_type: str, overnight: str):
    """Get daily statistical analysis"""
    # Run retrieve_daily_stats.py
    ...

bot.run(secrets['discord_bot_token'])
```

## Available Commands (Planned)

| Command | Description | Example |
|---------|-------------|---------|
| `!bias <ticker>` | Daily bias + ICT chart | `!bias NQ1` |
| `!stats <ticker> <prev> <overnight>` | Statistical probabilities | `!stats NQ1 Trend Bullish` |
| `!levels <ticker>` | Key price levels | `!levels ES1` |
| `!calendar` | Economic events today | `!calendar` |
| `!weekly <ticker>` | Weekly profile analysis | `!weekly NQ1` |
| `!help` | List all commands | `!help` |

## Advanced: Natural Language (LLM Integration)

For more conversational queries like *"What should I look for in NQ tomorrow?"*:

```python
import openai

async def parse_intent(message: str) -> dict:
    """Use LLM to understand user intent"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": """
                You are a trading assistant parser. Extract:
                - action: bias|stats|levels|calendar|weekly
                - ticker: NQ1|ES1|CL1|etc
                - date: tomorrow|today|YYYY-MM-DD
            """},
            {"role": "user", "content": message}
        ]
    )
    return json.loads(response.choices[0].message.content)
```

## Hosting Options

| Option | Pros | Cons | Cost |
|--------|------|------|------|
| **Your PC** | Free, easy access to data | Must keep PC on | $0 |
| **Raspberry Pi** | Low power, always on | Limited compute | ~$50 one-time |
| **VPS (DigitalOcean)** | 24/7, reliable | Need to sync data | $5-10/mo |
| **Railway/Render** | Easy deploy | Limited free tier | Free-$5/mo |

## Security Considerations

1. **Token Security**: Never commit `secrets.json` to git
2. **Access Control**: Only invite bot to private servers
3. **Rate Limiting**: Add cooldowns to prevent abuse
4. **Command Permissions**: Restrict certain commands to specific roles

## Next Steps

1. [ ] Create Discord application and bot
2. [ ] Get bot token and add to `secrets.json`
3. [ ] Implement basic `discord_bot.py`
4. [ ] Add command handlers for each skill
5. [ ] Test in private server
6. [ ] Add LLM integration for natural language
7. [ ] Deploy to always-on host

## Related Files
- `scripts/utils/discord_notify.py` - Webhook notifications (already implemented)
- `discord_webhooks.json` - Webhook channel configuration
- `.agent/skills/discord_notifier/SKILL.md` - Notifier skill docs
