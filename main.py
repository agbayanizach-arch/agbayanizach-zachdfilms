import os
import re
import json
import random
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import discord
from discord.ext import commands
from discord import app_commands


TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "."
VOUCH_CHANNEL_ID = 1557995158060925050
VOUCH_MESSAGE = "Legit got Minecraft from <#1523004933815799929>"

CMD_CHANNEL_ID = 1557995226121895936
TICKET_CHANNEL_ID = 1555782121598095380

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(
    command_prefix=[".", "-"],
    intents=intents,
    help_command=None,
)

# Dynamic state (stored in memory; resets when the process restarts).
current_vanity = "your-vanity-here"
target_role_id = None
account_stock = []

active_gtn_games = {}
# Per-server automoderation settings and warning history persist across restarts.
AUTOMODE_FILE = "automode_settings.json"
automode_settings = {}
bot_invite_strikes = defaultdict(int)
recent_messages = defaultdict(deque)
recent_joins = defaultdict(deque)
recent_destructive_actions = defaultdict(deque)


def load_automode_settings():
    global automode_settings
    try:
        with open(AUTOMODE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        automode_settings = data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        automode_settings = {}


def save_automode_settings():
    try:
        with open(AUTOMODE_FILE, "w", encoding="utf-8") as file:
            json.dump(automode_settings, file, indent=2)
    except OSError as exc:
        print(f"Could not save automode settings: {exc}")


def automode_enabled(guild_id: int) -> bool:
    return bool(automode_settings.get(str(guild_id), {}).get("enabled", False))


load_automode_settings()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash command(s).")
    except Exception as exc:
        print(f"Failed to sync slash commands: {exc}")


# Automatically grant/remove the configured role as custom status changes.
@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    global target_role_id, current_vanity

    if not target_role_id or not current_vanity or after.bot:
        return

    reward_role = after.guild.get_role(target_role_id)
    if reward_role is None:
        return

    has_vanity = any(
        isinstance(activity, discord.CustomActivity)
        and isinstance(activity.name, str)
        and current_vanity.casefold() in activity.name.casefold()
        for activity in after.activities
    )
    has_role = reward_role in after.roles

    try:
        if has_vanity and not has_role:
            await after.add_roles(
                reward_role,
                reason="Required custom status detected",
            )
        elif not has_vanity and has_role:
            await after.remove_roles(
                reward_role,
                reason="Required custom status removed",
            )
    except discord.Forbidden:
        print(
            "Missing permissions or role hierarchy to update "
            f"role ID {target_role_id}."
        )
    except discord.HTTPException as exc:
        print(f"Could not update status role for {after}: {exc}")


# Usage: .genaccess <full required custom-status phrase> @Role
# Example: .genaccess .gg/V2NSJUb89P - Free MCFA Generator @YourRole
@bot.command(name="genaccess")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def genaccess(ctx: commands.Context, *, arguments: str):
    global current_vanity, target_role_id

    role_match = re.search(r"<@&(\d+)>\s*$", arguments)
    if role_match is None:
        await ctx.reply(
            "❌ End the command with a real role mention.\n"
            "Example: `.genaccess .gg/V2NSJUb89P - Free MCFA Generator @YourRole`",
            mention_author=False,
        )
        return

    phrase = arguments[:role_match.start()].strip()
    role = ctx.guild.get_role(int(role_match.group(1)))

    if not phrase:
        await ctx.reply(
            "❌ Please provide the full required custom-status phrase.",
            mention_author=False,
        )
        return

    if role is None or role.is_default() or role.managed:
        await ctx.reply(
            "❌ Choose a valid, assignable role from this server.",
            mention_author=False,
        )
        return

    if not ctx.guild.me or not ctx.guild.me.guild_permissions.manage_roles:
        await ctx.reply(
            "❌ I need the **Manage Roles** permission.",
            mention_author=False,
        )
        return

    if role >= ctx.guild.me.top_role:
        await ctx.reply(
            "❌ Move my highest role above the selected role, then try again.",
            mention_author=False,
        )
        return

    current_vanity = phrase
    target_role_id = role.id

    embed = discord.Embed(
        title="✨ How to Access Free Generator ✨",
        description=(
            "Follow these simple steps to get access to the Free MCFA Generator!\n\n"
            "🔮 **Step 1**\n"
            "Set your custom status to contain this phrase:\n"
            f"`{current_vanity}`\n\n"
            "🔸 **Step 2**\n"
            f"Go to <#{CMD_CHANNEL_ID}> and type:\n"
            "`.gen`\n\n"
            "✅ **Step 3**\n"
            "When your status matches, the selected role will be granted automatically.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📣 **Important Notes**\n"
            "❌ Don't ping any staff for this.\n"
            f"🎫 Need help? <#{TICKET_CHANNEL_ID}>\n"
            "⚠️ If the required phrase is removed, the role will be removed too."
        ),
        color=0x2B2D31,
    )
    embed.set_footer(text="WitherCloud Generator")
    await ctx.send(embed=embed)


# .gen
@bot.command(name="gen")
async def gen(ctx: commands.Context):
    if ctx.guild is None:
        await ctx.reply(
            "❌ This command can only be used in a server.",
            mention_author=False,
        )
        return

    if ctx.channel.id != CMD_CHANNEL_ID:
        await ctx.reply(
            f"❌ This command can only be used in <#{CMD_CHANNEL_ID}>.",
            mention_author=False,
        )
        return

    # The user's custom status is mandatory.
    has_vanity = any(
        isinstance(activity, discord.CustomActivity)
        and isinstance(activity.name, str)
        and current_vanity.casefold() in activity.name.casefold()
        for activity in getattr(ctx.author, "activities", [])
    )

    if not has_vanity:
        await ctx.reply(
            "❌ **Access Denied!** Your custom status must contain "
            f"`{current_vanity}` before you can use this generator.",
            mention_author=False,
        )
        return

    if not account_stock:
        await ctx.reply(
            "❌ Out of stock! Please ask an administrator to restock.",
            mention_author=False,
        )
        return

    # Give the configured reward role when possible.
    if target_role_id:
        reward_role = ctx.guild.get_role(target_role_id)
        if reward_role and reward_role not in ctx.author.roles:
            try:
                await ctx.author.add_roles(
                    reward_role,
                    reason="Valid generator vanity custom status",
                )
            except discord.Forbidden:
                print(
                    "Missing permissions: move the bot's role above "
                    f"role ID {target_role_id}."
                )
            except discord.HTTPException as exc:
                print(f"Could not assign generator role: {exc}")

    account = account_stock.pop(0)

    dm_embed = discord.Embed(
        title="✅ Account Generated",
        description=(
            "Your account has been generated successfully!\n\n"
            f"**Account:** ||`{discord.utils.escape_markdown(account)}`||\n\n"
            f"**Generated by:** {ctx.author.mention}\n\n"
            "Please keep your account details secure."
        ),
        color=discord.Color.green(),
    )
    dm_embed.set_footer(
        text=f"Generated by {bot.user.name if bot.user else 'WitherCloud'}"
    )

    try:
        await ctx.author.send(embed=dm_embed)
    except discord.Forbidden:
        account_stock.insert(0, account)
        await ctx.reply(
            "❌ I couldn't DM you. Enable direct messages from server members "
            "and try again. Your account was returned to stock.",
            mention_author=False,
        )
        return
    except discord.HTTPException as exc:
        account_stock.insert(0, account)
        print(f"Could not send generated account DM: {exc}")
        await ctx.reply(
            "❌ I couldn't send the account by DM. Your account was returned "
            "to stock; please try again later.",
            mention_author=False,
        )
        return

    await ctx.reply(
        "✅ **Account generated!** Check your Direct Messages.",
        mention_author=False,
    )


# /restock <file>
@bot.tree.command(
    name="restock",
    description="Restock accounts using a .txt file (one email:pass per line)",
)
@app_commands.describe(file="Upload a text file containing email:pass lines")
@app_commands.checks.has_permissions(administrator=True)
async def restock_slash(
    interaction: discord.Interaction,
    file: discord.Attachment,
):
    await interaction.response.defer(ephemeral=True)

    if not file.filename.lower().endswith(".txt"):
        await interaction.followup.send(
            "❌ Invalid file format. Please upload a `.txt` file.",
            ephemeral=True,
        )
        return

    try:
        content = (await file.read()).decode("utf-8-sig")
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        valid_accounts = [line for line in lines if ":" in line]

        if not valid_accounts:
            await interaction.followup.send(
                "❌ No valid `email:pass` account lines were found.",
                ephemeral=True,
            )
            return

        account_stock.extend(valid_accounts)

        await interaction.followup.send(
            f"✅ Successfully stocked **{len(valid_accounts)}** accounts! "
            f"Total inventory: **{len(account_stock)}**.",
            ephemeral=True,
        )
    except (UnicodeDecodeError, discord.HTTPException, OSError) as exc:
        print(f"Restock error: {exc}")
        await interaction.followup.send(
            "❌ Couldn't read that file. Please upload a UTF-8 `.txt` file.",
            ephemeral=True,
        )


@restock_slash.error
async def restock_slash_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.MissingPermissions):
        message = (
            "❌ Access denied. This command requires Administrator permissions."
        )
    else:
        print(f"/restock error: {error}")
        message = "❌ The restock command failed. Check the bot logs."

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@genaccess.error
async def admin_command_error(
    ctx: commands.Context,
    error: commands.CommandError,
):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(
            "❌ Access denied. This command requires Administrator permissions.",
            mention_author=False,
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(
            "❌ Usage: `.genaccess <full required custom-status phrase> @role`\n"
            "Example: `.genaccess .gg/V2NSJUb89P - Free MCFA Generator @YourRole`",
            mention_author=False,
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(
            "❌ I couldn't find that role. Mention the actual role using "
            "Discord's role picker.\n"
            "Example: `.genaccess .gg/V2NSJUb89P - Free MCFA Generator @YourRole`",
            mention_author=False,
        )
    else:
        print(f".genaccess error: {error}")
        await ctx.reply(
            "❌ The command failed. Check the bot logs.",
            mention_author=False,
        )



# Apply automode protections to every human-authored server message when enabled.
DISCORD_INVITE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg/[\w-]+|discord(?:app)?\.com/invite/[\w-]+)", re.IGNORECASE)


@bot.event
async def on_message(message: discord.Message):
    if message.guild and not message.author.bot:
        guild = message.guild
        author = message.author

        if automode_enabled(guild.id) and isinstance(author, discord.Member):
            is_admin = author.guild_permissions.administrator or author.id == guild.owner_id
            if not is_admin:
                now = time.monotonic()
                key = (guild.id, author.id)
                bucket = recent_messages[key]
                bucket.append(now)
                while bucket and now - bucket[0] > 3:
                    bucket.popleft()

                if len(bucket) >= 3:
                    bucket.clear()
                    try:
                        await author.timeout(discord.utils.utcnow() + __import__('datetime').timedelta(minutes=2), reason="Automode: 3 messages within 3 seconds")
                        await message.channel.send(f"⏱️ {author.mention} was timed out for **2 minutes** for spam (3 messages within 3 seconds).", delete_after=8)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        print(f"Automode spam timeout failed: {exc}")

                # Delete Discord invites that point to a different server.
                match = DISCORD_INVITE_RE.search(message.content)
                if match:
                    invite_url = match.group(0)
                    if not invite_url.startswith("http"):
                        invite_url = "https://" + invite_url
                    external_invite = True
                    try:
                        invite = await bot.fetch_invite(invite_url, with_counts=False)
                        if invite.guild and invite.guild.id == guild.id:
                            external_invite = False
                    except (discord.NotFound, discord.HTTPException, discord.InvalidArgument):
                        # Invalid/unknown invites are treated as external to avoid link advertising.
                        external_invite = True
                    if external_invite:
                        try:
                            await message.delete()
                        except (discord.Forbidden, discord.HTTPException):
                            pass
                        try:
                            await author.timeout(discord.utils.utcnow() + __import__('datetime').timedelta(minutes=2), reason="Automode: external Discord invite link")
                            await message.channel.send(f"🔗 {author.mention} was timed out for **2 minutes** for posting an invite to another server.", delete_after=8)
                        except (discord.Forbidden, discord.HTTPException) as exc:
                            print(f"Automode invite timeout failed: {exc}")

    await bot.process_commands(message)


# -gtn <prize> <maxnumber>, for example: -gtn Minecraft Account 500
@bot.command(name="gtn")
@commands.guild_only()
async def guess_the_number(ctx: commands.Context, *, arguments: str):
    parts = arguments.rsplit(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await ctx.reply(
            "❌ Usage: `-gtn <prize> <maxnumber>`\\n"
            "Example: `-gtn Minecraft Account 500`",
            mention_author=False,
        )
        return

    prize = parts[0].strip()
    maximum = int(parts[1])
    if not prize:
        await ctx.reply("❌ Please specify a prize.", mention_author=False)
        return
    if not 1 <= maximum <= 1000:
        await ctx.reply("❌ The maximum number must be between **1 and 1000**.", mention_author=False)
        return

    if not ctx.guild.me or not ctx.guild.me.guild_permissions.manage_channels:
        await ctx.reply("❌ I need the **Manage Channels** permission to lock and unlock this channel.", mention_author=False)
        return

    channel = ctx.channel
    if not isinstance(channel, discord.TextChannel):
        await ctx.reply("❌ This game can only be started in a text channel.", mention_author=False)
        return

    # Choose the secret answer randomly and send it only to the command user by DM.
    answer = random.randint(1, maximum)
    try:
        secret_embed = discord.Embed(
            title="🔐 Your GTN Secret Number",
            description=(
                f"Your Guess the Number game has started in **{ctx.guild.name}**.\\n"
                f"**Secret number:** `{answer}`\\n"
                f"**Prize:** {prize}\\n"
                f"**Range:** 1–{maximum}\\n\\n"
                "Keep this number private so members can play fairly."
            ),
            color=5763719,
        )
        secret_embed.set_footer(text="GTN Event Manager • Only visible to the host")
        await ctx.author.send(embed=secret_embed)
    except discord.Forbidden:
        await ctx.reply(
            "❌ I couldn't DM you the secret number. Enable DMs from server members and run the command again; the game was not started.",
            mention_author=False,
        )
        return
    except discord.HTTPException as exc:
        print(f"Could not DM GTN secret number: {exc}")
        await ctx.reply(
            "❌ I couldn't send you the secret number by DM, so the game was not started. Please try again.",
            mention_author=False,
        )
        return

    # Enable chat when the game starts.
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    try:
        await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrite,
            reason="Starting Guess the Number event",
        )
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Could not enable GTN channel: {exc}")
        await ctx.reply("❌ I couldn't enable this channel. Check my permissions and try again.", mention_author=False)
        return

    active_gtn_games[channel.id] = {
        "answer": answer,
        "prize": prize,
        "maximum": maximum,
    }

    # Keep the existing GTN embed layout unchanged; only its range value is dynamic.
    embed = discord.Embed(
        title="🎉 GUESS THE NUMBER STARTED! 🎉",
        description="A new game has begun! Be the first to guess the correct number to win.",
        color=5763719,
    )
    embed.add_field(name="🔢 Number Range", value=f"Between `1` and `{maximum}`", inline=True)
    embed.add_field(name="🔒 Winning Condition", value="Channel locks automatically upon correct answer.", inline=True)
    embed.add_field(name="🏆 Prize", value=prize, inline=False)
    embed.set_footer(text="GTN Event Manager • Type your guess directly in the chat!")
    await ctx.send(embed=embed)
    await ctx.reply("✅ Game started! I've sent the secret number to your DMs.", mention_author=False)


@bot.listen("on_message")
async def handle_gtn_guess(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    game = active_gtn_games.get(message.channel.id)
    if not game or not message.content.strip().isdigit():
        return

    guess = int(message.content.strip())
    if not 1 <= guess <= game["maximum"] or guess != game["answer"]:
        return

    active_gtn_games.pop(message.channel.id, None)
    embed = discord.Embed(
        title="🎉 NUMBER GUESSED CORRECTLY! 🎉",
        description=(
            f"Congratulations {message.author.mention}! You guessed **{game['answer']}** "
            f"first and won **{game['prize']}**!"
        ),
        color=5763719,
    )
    embed.set_footer(text="GTN Event Manager • Game ended")

    try:
        await message.channel.send(embed=embed)
        if isinstance(message.channel, discord.TextChannel):
            overwrite = message.channel.overwrites_for(message.guild.default_role)
            overwrite.send_messages = False
            await message.channel.set_permissions(
                message.guild.default_role,
                overwrite=overwrite,
                reason="Guess the Number winner found the answer",
            )
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Could not announce or lock GTN channel: {exc}")


# -automode on / -automode off — server administrators enable or disable protections.
@bot.command(name="automode")
@commands.guild_only()
@commands.has_guild_permissions(administrator=True)
async def automode_command(ctx: commands.Context, mode: str):
    normalized = mode.casefold()
    if normalized not in {"on", "off", "enable", "enabled", "disable", "disabled"}:
        await ctx.reply("Usage: `-automode on` or `-automode off`", mention_author=False)
        return
    enabled = normalized in {"on", "enable", "enabled"}
    automode_settings[str(ctx.guild.id)] = {"enabled": enabled}
    save_automode_settings()
    if enabled:
        await ctx.send(
            "✅ **Automode enabled for this server.**\n"
            "• Anti-spam: 3 messages within 3 seconds → 2-minute timeout\n"
            "• External Discord invite links: delete and 2-minute timeout\n"
            "• New bots: kick attempt and warn the inviter by DM\n"
            "• Basic anti-raid / anti-nuke monitoring is enabled; keep trusted staff roles limited."
        )
    else:
        await ctx.send("🛡️ **Automode disabled** for this server.")


@automode_command.error
async def automode_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ Only server administrators can change automode.", mention_author=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Usage: `-automode on` or `-automode off`", mention_author=False)
    else:
        print(f"-automode error: {error}")
        await ctx.reply("❌ Couldn't change automode. Check the bot logs.", mention_author=False)


# When automode is enabled, kick newly added bots (except the bot itself) and track the inviter.
@bot.event
async def on_member_join(member: discord.Member):
    if not member.bot or not automode_enabled(member.guild.id) or (bot.user and member.id == bot.user.id):
        return
    guild = member.guild
    inviter = None
    try:
        async for entry in guild.audit_logs(limit=8, action=discord.AuditLogAction.bot_add):
            if entry.target and entry.target.id == member.id:
                inviter = entry.user
                break
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Could not inspect bot-add audit log: {exc}")

    try:
        await member.kick(reason="Automode: bots are not allowed without an exception")
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Automode could not kick bot {member.id}: {exc}")

    if isinstance(inviter, discord.Member) and not inviter.guild_permissions.administrator and inviter.id != guild.owner_id:
        bot_invite_strikes[(guild.id, inviter.id)] += 1
        strikes = bot_invite_strikes[(guild.id, inviter.id)]
        try:
            if strikes <= 3:
                await inviter.send(f"⚠️ Warning {strikes}/3 for adding a bot to **{guild.name}** while automode is enabled. The bot was removed. Another attempt after these 3 warnings may result in a 1-day timeout.")
            else:
                await inviter.timeout(discord.utils.utcnow() + __import__('datetime').timedelta(days=1), reason="Automode: repeatedly adding bots")
                await inviter.send(f"⛔ You were timed out for **1 day** in **{guild.name}** for repeatedly adding bots after 3 warnings.")
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"Could not warn/timeout bot inviter: {exc}")


async def _check_destructive_action(guild: discord.Guild, action: discord.AuditLogAction, target_id: int, label: str):
    if not automode_enabled(guild.id):
        return
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if entry.target and entry.target.id == target_id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 12:
                actor = entry.user
                if not isinstance(actor, discord.Member) or actor.id == guild.owner_id or actor.guild_permissions.administrator:
                    return
                key = (guild.id, actor.id)
                now = time.monotonic()
                bucket = recent_destructive_actions[key]
                bucket.append(now)
                while bucket and now - bucket[0] > 10:
                    bucket.popleft()
                if len(bucket) >= 2:
                    await actor.timeout(discord.utils.utcnow() + __import__('datetime').timedelta(days=1), reason=f"Automode anti-nuke: repeated {label} actions")
                    try:
                        await actor.send(f"⛔ You were timed out for **1 day** in **{guild.name}** after repeated {label} actions triggered the anti-nuke safeguard.")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                return
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"Could not inspect {label} audit log: {exc}")


@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    await _check_destructive_action(channel.guild, discord.AuditLogAction.channel_delete, channel.id, "channel deletion")


@bot.event
async def on_guild_role_delete(role: discord.Role):
    await _check_destructive_action(role.guild, discord.AuditLogAction.role_delete, role.id, "role deletion")

# Render health-check web server.
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"WitherCloud Generator Bot is running!")

    def log_message(self, format, *args):
        pass


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Health server listening on 0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "Set the DISCORD_TOKEN environment variable before starting the bot."
        )

    Thread(target=run_web_server, daemon=True).start()
    bot.run(TOKEN)
