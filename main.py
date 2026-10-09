import os
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "-"
VOUCH_CHANNEL_ID = 1555778546046206002

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


def payout_embed(email: str, password: str) -> discord.Embed:
    embed = discord.Embed(
        title="Here is your Account",
        description=(
            "**Email:**\n||```\n" + email + "\n```||\n\n"
            "**Pass:**\n||```\n" + password + "\n```||\n\n"
            f"Legit or Not? Please vouch on <#{VOUCH_CHANNEL_ID}>"
        ),
        color=discord.Color.green(),
    )
    embed.set_footer(text="WitherCloud Generator")
    return embed


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


@bot.command(name="payout")
@commands.has_guild_permissions(manage_channels=True)
async def payout(ctx: commands.Context, ticket_channel: discord.TextChannel, *, credentials: str):
    """Usage: -payout #ticket email:pass"""
    if ctx.guild is None or ticket_channel.guild.id != ctx.guild.id:
        await ctx.reply("❌ Please mention a ticket channel in this server.", mention_author=False)
        return

    if ":" not in credentials:
        await ctx.reply("❌ Format: `-payout #ticket email:pass`", mention_author=False)
        return

    email, password = credentials.split(":", 1)
    email = email.strip()
    password = password.strip()
    if not email or not password:
        await ctx.reply("❌ Both email and password are required. Format: `-payout #ticket email:pass`", mention_author=False)
        return

    me = ctx.guild.me
    if me is None or not ticket_channel.permissions_for(me).send_messages:
        await ctx.reply("❌ I don't have permission to send messages in that ticket channel.", mention_author=False)
        return
    if me is None or not ticket_channel.permissions_for(me).manage_channels:
        await ctx.reply("❌ I need Manage Channels permission to delete the ticket afterward.", mention_author=False)
        return

    try:
        await ticket_channel.send(embed=payout_embed(email, password))
    except discord.Forbidden:
        await ctx.reply("❌ I couldn't send the payout embed. Check my channel permissions.", mention_author=False)
        return
    except discord.HTTPException:
        await ctx.reply("❌ Discord couldn't send the payout embed, so the ticket was not deleted.", mention_author=False)
        return

    # Allow a few seconds for the recipient to see the payout before deleting the ticket.
    await ctx.reply(f"✅ Payout sent to {ticket_channel.mention}. Deleting that ticket in 5 seconds.", mention_author=False)
    await asyncio.sleep(5)
    try:
        await ticket_channel.delete(reason=f"Ticket payout completed by {ctx.author} ({ctx.author.id})")
    except discord.Forbidden:
        await ctx.send("⚠️ The payout was sent, but I couldn't delete the ticket. Check my Manage Channels permission.")
    except discord.HTTPException:
        await ctx.send("⚠️ The payout was sent, but Discord failed to delete the ticket.")


@payout.error
async def payout_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ You need the **Manage Channels** permission to use `-payout`.", mention_author=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Usage: `-payout #ticket email:pass`", mention_author=False)
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("❌ I couldn't find that ticket channel. Mention it like `#ticket`.", mention_author=False)
    else:
        print(f"Payout command error: {error!r}")
        await ctx.reply("❌ Something went wrong while processing the payout.", mention_author=False)


# Render Web Service health endpoint.
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"WitherCloud Payout Bot is running!")

    def log_message(self, format, *args):
        pass


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server listening on 0.0.0.0:{port}")
    server.serve_forever()


if not TOKEN:
    raise RuntimeError("Set the DISCORD_TOKEN environment variable before starting the bot.")

Thread(target=run_web_server, daemon=True).start()
bot.run(TOKEN)
