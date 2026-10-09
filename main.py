import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "-"
VOUCH_CHANNEL_ID = 1555778546046206002

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ticket channel ID -> expected customer ID.
# Pending payouts are in memory only and reset when the bot restarts.
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
async def payout(
    ctx: commands.Context,
    ticket_channel: discord.TextChannel,
    customer: discord.Member,
    *,
    credentials: str,
):
    """
    Usage: -payout #ticket @customer email:pass
    Explicitly mention the customer so the bot never has to guess ticket ownership.
    """
    if ctx.guild is None or ticket_channel.guild.id != ctx.guild.id:
        await ctx.reply(
            "❌ Please mention a ticket channel in this server.",
            mention_author=False,
        )
        return

    if customer.bot:
        await ctx.reply("❌ The ticket customer must be a human member.", mention_author=False)
        return

    if ":" not in credentials:
        await ctx.reply(
            "❌ Format: `-payout #ticket @customer email:pass`",
            mention_author=False,
        )
        return

    email, password = credentials.split(":", 1)
    email, password = email.strip(), password.strip()
    if not email or not password:
        await ctx.reply(
            "❌ Both email and password are required. Format: `-payout #ticket @customer email:pass`",
            mention_author=False,
        )
        return

    me = ctx.guild.me
    if me is None:
        await ctx.reply("❌ I couldn't resolve my bot member in this server.", mention_author=False)
        return

    permissions = ticket_channel.permissions_for(me)
    if not permissions.view_channel or not permissions.send_messages:
        await ctx.reply(
            "❌ I need **View Channel** and **Send Messages** permissions in that ticket.",
            mention_author=False,
        )
        return

    if not permissions.manage_channels:
        await ctx.reply(
            "❌ I need **Manage Channels** permission to delete the ticket after the customer's vouch.",
            mention_author=False,
        )
        return

    if VOUCH_CHANNEL_ID not in {channel.id for channel in ctx.guild.text_channels}:
        await ctx.reply(
            "❌ The configured vouch channel isn't available in this server. Check `VOUCH_CHANNEL_ID`.",
            mention_author=False,
        )
        return

    # Do not overwrite a pending payout for the same ticket without warning.
    if ticket_channel.id in pending_vouches:
        await ctx.reply(
            f"⚠️ {ticket_channel.mention} already has a pending vouch for <@{pending_vouches[ticket_channel.id]}>. "
            "No new payout was sent.",
            mention_author=False,
        )
        return

    try:
        await ticket_channel.send(embed=payout_embed(email, password))
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Could not send payout embed: {exc!r}")
        await ctx.reply(
            "❌ I couldn't send the payout embed, so no vouch or deletion was scheduled.",
            mention_author=False,
        )
        return

    pending_vouches[ticket_channel.id] = customer.id
    await ctx.reply(
        f"✅ Payout sent to {ticket_channel.mention} for {customer.mention}. "
        f"The ticket will stay open until that exact customer posts a message containing **vouch** "
        f"in <#{VOUCH_CHANNEL_ID}>. Only that customer can trigger deletion.",
        mention_author=False,
    )


@bot.event
async def on_message(message: discord.Message):
    if (
        not message.author.bot
        and message.guild is not None
        and message.channel.id == VOUCH_CHANNEL_ID
        and re.search(r"\bvouch\b", message.content, flags=re.IGNORECASE)
    ):
        customer_id = message.author.id

        # A customer may have more than one paid ticket. Do not arbitrarily delete
        # one if more than one ticket is pending for the same customer.
        matching_ticket_ids = [
            ticket_id
            for ticket_id, expected_customer_id in pending_vouches.items()
            if expected_customer_id == customer_id
        ]

        if len(matching_ticket_ids) == 1:
            ticket_id = matching_ticket_ids[0]
            ticket_channel = message.guild.get_channel(ticket_id)

            if isinstance(ticket_channel, discord.TextChannel):
                try:
                    await ticket_channel.delete(
                        reason=f"Ticket customer {message.author} ({message.author.id}) vouched after payout"
                    )
                except discord.Forbidden:
                    await message.channel.send(
                        f"⚠️ Vouch received from {message.author.mention}, but I couldn't delete "
                        f"the ticket. Check my **Manage Channels** permission."
                    )
                except discord.HTTPException as exc:
                    print(f"Could not delete paid ticket: {exc!r}")
                    await message.channel.send(
                        "⚠️ Vouch received, but Discord failed to delete the ticket."
                    )
                else:
                    await message.reply(
                        "✅ Vouch verified. The matching paid ticket has been closed.",
                        mention_author=False,
                    )
                    pending_vouches.pop(ticket_id, None)
            else:
                # The ticket was already deleted or is no longer accessible.
                pending_vouches.pop(ticket_id, None)

        elif len(matching_ticket_ids) > 1:
            await message.reply(
                "⚠️ Your vouch was received, but you have multiple pending paid tickets. "
                "Please contact staff so the correct ticket can be closed safely.",
                mention_author=False,
            )

    await bot.process_commands(message)


@payout.error
async def payout_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(
            "❌ You need the **Manage Channels** permission to use `-payout`.",
            mention_author=False,
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(
            "Usage: `-payout #ticket @customer email:pass`",
            mention_author=False,
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(
            "❌ I couldn't resolve the ticket channel or customer. Mention both: "
            "`-payout #ticket @customer email:pass`.",
            mention_author=False,
        )
    else:
        print(f"Payout command error: {error!r}")
        await ctx.reply(
            "❌ Something went wrong while processing the payout. Check the bot logs.",
            mention_author=False,
        )


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
