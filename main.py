import discord
from discord.ext import commands
import asyncio
import os
from flask import Flask
from threading import Thread

# 1. Create a fake web server to satisfy Render's Free Web Service requirements
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    # Render automatically passes a port number via environment variables
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# 2. Main Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'🤖 Bot logged in as {bot.user.name}')
    try:
        await bot.load_extension('checker_cog')
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Setup error: {e}")

async def main():
    # Start the web server thread before running the bot
    keep_alive()
    
    token = os.getenv('DISCORD_TOKEN')
    if token:
        await bot.start(token)
    else:
        print("❌ Error: No DISCORD_TOKEN found in Environment Variables!")

if __name__ == "__main__":
    asyncio.run(main())
