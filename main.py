import os
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import discord
from discord.ext import commands
from discord import app_commands

# Safe WitherCloud Generator bot template.
# This replaces the previous command set and does NOT distribute account credentials.
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = '-'
COMMAND_CHANNEL_ID = 1555780870839861258
HELP_CHANNEL_ID = 1555782121598095380
VOUCH_CHANNEL_ID = 1557907049558446131
CONFIG_FILE = 'withercloud_config.json'
ACCESS_FILE = 'withercloud_access.json'

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def config():
    return load_json(CONFIG_FILE, {'required_status': os.getenv('REQUIRED_CUSTOM_STATUS', '').strip(), 'vanity': '', 'stock_count': 0})


def access_data():
    return load_json(ACCESS_FILE, {})


def has_required_status(member: discord.Member, required: str) -> bool:
    if not required:
        return False
    wanted = required.strip().casefold()
    for activity in getattr(member, 'activities', []):
        if isinstance(activity, discord.CustomActivity):
            state = (activity.state or '').strip().casefold()
            if state == wanted:
                return True
    return False


def green_embed(title: str, description: str = '') -> discord.Embed:
    return discord.Embed(title=title, description=description, color=discord.Color.green())


def access_embed() -> discord.Embed:
    data = config()
    required_status = (data.get("required_status") or "").strip()
    status_text = f"`{required_status}`" if required_status else "`Not configured yet`"

    embed = green_embed(
        "How to Access WitherCloud Generator",
        "Follow these simple steps to get access to the **WitherCloud Generator**!"
    )
    embed.add_field(
        name="🪄 Step 1",
        value=f"Set your Discord custom status to:\n{status_text}",
        inline=False,
    )
    embed.add_field(
        name="🌟 Step 2",
        value=f"Go to <#{COMMAND_CHANNEL_ID}> and type:\n`-cstatus`",
        inline=False,
    )
    embed.add_field(
        name="✅ Step 3",
        value="You're done! If your custom status matches, the bot will confirm your access.",
        inline=False,
    )
    embed.add_field(
        name="📚 Important Notes",
        value=(
            "❌ Don't ping staff for access.\n"
            f"🎟️ Need help? <#{HELP_CHANNEL_ID}>\n"
            "⚠️ An incorrect custom status means access won't be verified."
        ),
        inline=False,
    )
    embed.set_footer(text="WitherCloud Generator")
    return embed


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except discord.HTTPException:
        pass
    print(f'Logged in as {bot.user} ({bot.user.id})')


@bot.command(name='help')
async def help_command(ctx):
    await ctx.send(embed=access_embed())



@bot.command(name='cstatusset')
@commands.has_permissions(administrator=True)
async def cstatusset(ctx, *, status: str):
    data = config()
    data['required_status'] = status.strip()
    save_json(CONFIG_FILE, data)
    embed = green_embed(
        'WitherCloud Generator',
        f'✅ Required custom status set to:\\n`{status.strip()}`'
    )
    embed.set_footer(text='WitherCloud Generator')
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name='cstatus')
async def cstatus(ctx):
    data = config()
    required = (data.get('required_status') or os.getenv('REQUIRED_CUSTOM_STATUS', '')).strip()
    if isinstance(ctx.author, discord.Member) and has_required_status(ctx.author, required):
        embed = green_embed(
            'WitherCloud Generator',
            '✅ **Access Verified Successfully!**\\nYour custom status matches. You have passed the access check.'
        )
    else:
        embed = green_embed(
            'WitherCloud Generator',
            '❌ **Access Not Granted**\\nYour custom status does not match the required status. Set it exactly as configured and try again.'
        )
    embed.set_footer(text='WitherCloud Generator')
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name='gen')
async def gen(ctx):
    data = config()
    if not isinstance(ctx.author, discord.Member) or not has_required_status(
        ctx.author, (data.get('required_status') or os.getenv('REQUIRED_CUSTOM_STATUS', '')).strip()
    ):
        embed = green_embed(
            'WitherCloud Generator',
            '❌ **Access Not Granted**\\nSet the required custom status and run `-cstatus` first.'
        )
        embed.set_footer(text='WitherCloud Generator')
        await ctx.reply(embed=embed, mention_author=False)
        return

    stock_count = max(0, int(data.get('stock_count', 0)))
    if stock_count <= 0:
        embed = green_embed(
            'WitherCloud Generator',
            '📈 **Currently Out of Stock**\\nWait until it restock.'
        )
        embed.set_footer(text='WitherCloud Generator')
        await ctx.reply(embed=embed, mention_author=False)
        return

    embed = green_embed(
        'WitherCloud Generator',
        f'✅ **Stock Available**\\nCurrently available: `{stock_count}`. This bot template tracks stock only and does not distribute account credentials.'
    )
    embed.set_footer(text='WitherCloud Generator')
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name='stock')
async def stock(ctx):
    data = config()
    stock_count = max(0, int(data.get('stock_count', 0)))
    embed = green_embed(
        'Stock',
        f'We currently have:\\n```{stock_count}``` Stock now.'
    )
    embed.set_footer(text='WitherCloud Generator')
    await ctx.reply(embed=embed, mention_author=False)


@bot.tree.command(name='restock', description='Add units to the displayed stock count')
@app_commands.describe(amount='Number of units to add to stock')
@app_commands.checks.has_permissions(administrator=True)
async def restock(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 1000000]):
    data = config()
    data['stock_count'] = max(0, int(data.get('stock_count', 0))) + amount
    save_json(CONFIG_FILE, data)
    embed = green_embed(
        'WitherCloud Generator',
        f'✅ Stock updated. Added `{amount}` units.\\nCurrent stock: `{data["stock_count"]}`'
    )
    embed.set_footer(text='WitherCloud Generator')
    await interaction.response.send_message(embed=embed, ephemeral=False)


@restock.error
async def restock_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = '❌ You need Administrator permission to use `/restock`.'
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    else:
        raise error


@bot.tree.command(name='genaccess', description='Show WitherCloud Generator access instructions')
@app_commands.describe(vanity='Optional vanity/status value to display in the instructions')
async def genaccess(interaction: discord.Interaction, vanity: str = ''):
    embed = access_embed()
    if vanity.strip():
        embed.add_field(name='Configured vanity', value=f'`{vanity.strip()}`', inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=False)





@cstatusset.error
async def cstatusset_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=green_embed(
            'WitherCloud Generator',
            '❌ You need Administrator permission to use `-cstatusset`.'
        ))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Usage: `-cstatusset your exact custom status`')
    else:
        raise error




# Render Web Service health endpoint.
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"WitherCloud Generator is running!")

    def log_message(self, format, *args):
        pass


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server listening on 0.0.0.0:{port}")
    server.serve_forever()


Thread(target=run_web_server, daemon=True).start()


if not TOKEN:
    raise RuntimeError('Set the DISCORD_TOKEN environment variable before starting the bot.')
bot.run(TOKEN)
