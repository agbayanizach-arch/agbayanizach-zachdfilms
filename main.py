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
    return load_json(CONFIG_FILE, {'required_status': '', 'vanity': ''})


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
    embed = green_embed('How to Access WitherCloud Generator',
        'Follow these simple steps to verify access to **WitherCloud Generator**!')
    embed.add_field(name='🪄 Step 1', value='Set your Discord custom status to the exact status configured by the server staff.', inline=False)
    embed.add_field(name='🌟 Step 2', value=f'Go to <#{COMMAND_CHANNEL_ID}> and type `-cstatus`.', inline=False)
    embed.add_field(name='✅ Step 3', value='If your status matches, the bot will confirm your access.', inline=False)
    embed.add_field(name='📚 Important Notes', value=f'❌ Do not ping staff for access.\n🎟️ Need help? <#{HELP_CHANNEL_ID}>', inline=False)
    embed.set_footer(text='WitherCloud Generator')
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
    await ctx.send(embed=green_embed('WitherCloud Generator', f'Required custom status set to:\n`{status.strip()}`'))


@bot.command(name='vanity')
@commands.has_permissions(administrator=True)
async def vanity(ctx, *, vanity_name: str):
    data = config()
    data['vanity'] = vanity_name.strip()
    save_json(CONFIG_FILE, data)
    await ctx.send(embed=green_embed('WitherCloud Generator', f'Access vanity requirement set to:\n`{vanity_name.strip()}`'))


@bot.command(name='cstatus')
async def cstatus(ctx):
    data = config()
    required = data.get('required_status', '')
    if not isinstance(ctx.author, discord.Member) or not has_required_status(ctx.author, required):
        embed = green_embed('WitherCloud Generator', '❌ Your custom status does not match the required status. Set it exactly as configured, then try again.')
        embed.set_footer(text='WitherCloud Generator')
        await ctx.send(embed=embed)
        return
    embed = green_embed('WitherCloud Generator', '**✅ You have Access to Generator Successfully**\nYou can use the `-gen` command now.')
    embed.set_footer(text='WitherCloud Generator')
    await ctx.send(embed=embed)


@bot.command(name='gen')
async def gen(ctx):
    data = config()
    if not isinstance(ctx.author, discord.Member) or not has_required_status(ctx.author, data.get('required_status', '')):
        await ctx.send(embed=green_embed('WitherCloud Generator', '❌ Access not verified. Set the required custom status and run `-cstatus` first.'))
        return
    # Deliberately no email:password credential distribution or account-file dispensing.
    try:
        await ctx.author.send(embed=green_embed('WitherCloud Generator', '✅ Your access is verified. This bot template does not distribute account credentials.\n\nPlease vouch in <#%s>.' % VOUCH_CHANNEL_ID))
        await ctx.reply('📩 Check your DMs, bro!', mention_author=False)
    except discord.Forbidden:
        await ctx.reply('I could not DM you. Please enable DMs from server members.', mention_author=False)


@bot.command(name='stock')
async def stock(ctx):
    await ctx.send(embed=green_embed('WitherCloud Generator', 'Account stock display is disabled in this safe template because it is not connected to a credential-distribution system.'))


@bot.command(name='restock')
@commands.has_permissions(administrator=True)
async def restock(ctx, *, filename: str = ''):
    await ctx.send(embed=green_embed('WitherCloud Generator', 'Credential-file restocking is not implemented in this template.'))


@bot.tree.command(name='genaccess', description='Show WitherCloud Generator access instructions')
@app_commands.describe(vanity='Optional vanity/status value to display in the instructions')
async def genaccess(interaction: discord.Interaction, vanity: str = ''):
    embed = access_embed()
    if vanity.strip():
        embed.add_field(name='Configured vanity', value=f'`{vanity.strip()}`', inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@cstatusset.error
@vanity.error
@restock.error
async def admin_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=green_embed('WitherCloud Generator', '❌ You need Administrator permission to use this command.'))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Please provide the required value.')
    else:
        raise error



# Render Web Service health endpoint: bind to 0.0.0.0 and Render's PORT.
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
