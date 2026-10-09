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

# ticket channel ID -> expected customer user ID. Pending payouts are kept in
# memory while the bot is running; after a restart, run -payout again if needed.
pending_vouches: dict[int, int] = {}


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
    """Usage: -payout #ticket email:pass; delete only after the ticket customer vouches."""
    if ctx.guild is None or ticket_channel.guild.id != ctx.guild.id:
        await ctx.reply("❌ Please mention a ticket channel in this server.", mention_author=False)
        return

    if ":" not in credentials:
        await ctx.reply("❌ Format: `-payout #ticket email:pass`", mention_author=False)
        return

    email, password = credentials.split(":", 1)
    email, password = email.strip(), password.strip()
    if not email or not password:
        await ctx.reply("❌ Both email and password are required. Format: `-payout #ticket email:pass`", mention_author=False)
        return

    me = ctx.guild.me
    if me is None or not ticket_channel.permissions_for(me).send_messages:
        await ctx.reply("❌ I don't have permission to send messages in that ticket channel.", mention_author=False)
        return
    if not ticket_channel.permissions_for(me).manage_channels:
        await ctx.reply("❌ I need Manage Channels permission to delete the ticket afterward.", mention_author=False)
        return

    # Identify the ticket customer. Ticket systems vary: some set View Channel,
    # others set Send Messages, and staff may also have member overwrites. First
    # use explicit member overwrites while excluding anyone with effective staff
    # permissions; if that is ambiguous, inspect recent channel messages and
    # select a non-staff human who has spoken in the ticket.
    candidates: dict[int, discord.Member] = {}
    for target, overwrite in ticket_channel.overwrites.items():
        if not isinstance(target, discord.Member) or target.bot:
            continue
        effective = ticket_channel.permissions_for(target)
        if effective.administrator or effective.manage_channels or effective.manage_messages:
            continue
        if overwrite.view_channel is True or overwrite.send_messages is True:
            candidates[target.id] = target

    if len(candidates) != 1:
        recent_speakers: dict[int, discord.Member] = {}
        try:
            async for old_message in ticket_channel.history(limit=100, oldest_first=False):
                author = old_message.author
                if not isinstance(author, discord.Member) or author.bot:
                    continue
                effective = ticket_channel.permissions_for(author)
                if effective.administrator or effective.manage_channels or effective.manage_messages:
                    continue
                recent_speakers[author.id] = author
                if len(recent_speakers) >= 10:
                    break
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"Could not inspect ticket history for customer identification: {exc!r}")

        # Prefer a unique non-staff user with a member-specific channel overwrite.
        # Otherwise use the most recent non-staff human who spoke in the ticket.
        if len(candidates) == 1:
            customer = next(iter(candidates.values()))
        elif recent_speakers:
            customer = next(iter(recent_speakers.values()))
        else:
            await ctx.reply(
                "❌ I still couldn't identify the ticket customer. Make sure the ticket owner has sent a message in the ticket, "
                "and that I have **View Channel** and **Read Message History** permissions. "
                "I haven't sent the payout or scheduled deletion.",
                mention_author=False,
            )
            return
    else:
        customer = next(iter(candidates.values()))
    try:
        await ticket_channel.send(embed=payout_embed(email, password))
    except (discord.Forbidden, discord.HTTPException) as exc:
        await ctx.reply("❌ I couldn't send the payout embed, so the ticket was not scheduled for deletion.", mention_author=False)
        print(f"Could not send payout embed: {exc!r}")
        return

    pending_vouches[ticket_channel.id] = customer.id
    await ctx.reply(
        f"✅ Payout sent to {ticket_channel.mention}. The ticket will stay open until {customer.mention} "
        f"posts a message containing **vouch** in <#{VOUCH_CHANNEL_ID}>. Only that customer can trigger deletion.",
        mention_author=False,
    )


@bot.event
async def on_message(message: discord.Message):
    # Wait for the customer assigned to a pending payout to vouch in the target channel.
    if (
        not message.author.bot
        and message.guild is not None
        and message.channel.id == VOUCH_CHANNEL_ID
        and "vouch" in message.content.casefold()
    ):
        customer_id = message.author.id
        matching_ticket_id = next(
            (ticket_id for ticket_id, expected_customer_id in pending_vouches.items()
             if expected_customer_id == customer_id),
            None,
        )
        if matching_ticket_id is not None:
            ticket_channel = message.guild.get_channel(matching_ticket_id)
            if isinstance(ticket_channel, discord.TextChannel):
                try:
                    await message.reply(
                        "✅ Vouch received from the ticket customer. Closing the paid ticket now.",
                        mention_author=False,
                    )
                    await ticket_channel.delete(
                        reason=f"Ticket customer {message.author} ({message.author.id}) vouched after payout"
                    )
                except discord.Forbidden:
                    await message.channel.send("⚠️ Vouch received, but I couldn't delete the ticket. Check my Manage Channels permission.")
                except discord.HTTPException as exc:
                    await message.channel.send("⚠️ Vouch received, but Discord failed to delete the ticket.")
                    print(f"Could not delete paid ticket: {exc!r}")
                finally:
                    pending_vouches.pop(matching_ticket_id, None)
            else:
                pending_vouches.pop(matching_ticket_id, None)

    await bot.process_commands(message)


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
