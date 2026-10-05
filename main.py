import discord
from discord.ext import commands
import asyncio
import os

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

# Reads your token safely from Render environments
token = os.getenv('DISCORD_TOKEN')
if token:
    bot.run(token)
else:
    print("❌ Error: No DISCORD_TOKEN found in Environment Variables!")
