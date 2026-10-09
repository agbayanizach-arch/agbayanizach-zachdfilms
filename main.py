import os
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from datetime import datetime, timedelta

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
    command_prefix=PREFIX,
    intents=intents,
    help_command=None,
)

# Dynamic state (stored in memory; resets when the process restarts).
current_vanity = "your-vanity-here"
target_role_id = None
account_stock = []
cooldowns = {}


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash command(s).")
    except Exception as exc:
        print(f"Failed to sync slash commands: {exc}")


# Automatically remove the reward role when the required status disappears.
@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    global target_role_id, current_vanity

    if not target_role_id:
        return

    reward_role = after.guild.get_role(target_role_id)
    if reward_role is None or reward_role not in after.roles:
        return

    has_vanity = any(
        isinstance(activity, discord.CustomActivity)
        and activity.name
        and current_vanity in activity.name
        for activity in after.activities
    )

    if not has_vanity:
        try:
            await after.remove_roles(
                reward_role,
                reason="Removed vanity from custom status",
            )
            print(
                f"Automatically removed role from {after.name}: "
                "required status was removed."
            )
        except discord.Forbidden:
            print(
                "Missing permissions: move the bot's role above "
                f"role ID {target_role_id}."
            )


# .genaccess <vanity> <@role>
# Example: .genaccess .gg/V2NSJUb89P @FreeNFA
# The vanity may contain dots and slashes; use a real role mention for roles
# whose names contain spaces.
@bot.command(name="genaccess")
@commands.has_permissions(administrator=True)
async def genaccess(
    ctx: commands.Context,
    vanity: str,
    *,
    role: discord.Role,
):
    global current_vanity, target_role_id

    current_vanity = vanity
    target_role_id = role.id

    embed = discord.Embed(
        title="✨ How to Access Free Generator ✨",
        description=(
            "Follow these simple steps to get access to the Free MCFA Generator!\n\n"
            "🔮 **Step 1**\n"
            "Set your custom status to:\n"
            f"`{current_vanity}`\n\n"
            "🔸 **Step 2**\n"
            f"Go to <#{CMD_CHANNEL_ID}> and type:\n"
            "`.gen`\n\n"
            "✅ **Step 3**\n"
            "You're done! 🎉 You now have access to the **Free Gen.**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📣 **Important Notes**\n"
            "❌ Don't ping any staff for this.\n"
            f"🎫 Need help? <#{TICKET_CHANNEL_ID}>\n"
            "⚠️ Improper custom status = No access granted."
        ),
        color=0x2B2D31,
    )
    embed.set_footer(text="WitherCloud Generator")
    await ctx.send(embed=embed)


# .gen
@bot.command(name="gen")
async def gen(ctx: commands.Context):
    if ctx.channel.id != CMD_CHANNEL_ID:
        await ctx.reply(
            f"❌ This command can only be used in <#{CMD_CHANNEL_ID}>.",
            mention_author=False,
        )
        return

    user_id = ctx.author.id

    # Enforce any active cooldown.
    if user_id in cooldowns:
        remaining = cooldowns[user_id] - datetime.utcnow()
        if remaining.total_seconds() > 0:
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            await ctx.reply(
                "❌ **Access Denied!** You failed to vouch previously. "
                f"You cannot generate for another **{hours}h {minutes}m**.",
                mention_author=False,
            )
            return
        del cooldowns[user_id]

    # Check the user's custom status.
    has_vanity = any(
        isinstance(activity, discord.CustomActivity)
        and activity.name
        and current_vanity in activity.name
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
    if target_role_id and ctx.guild:
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

    account = account_stock.pop(0)

    dm_embed = discord.Embed(
        title="✅ Account Generated",
        description=(
            "Your account has been generated successfully!\n\n"
            f"**Account:** ||`{discord.utils.escape_markdown(account)}`||\n\n"
            f"**Generated by:** {ctx.author.mention}\n\n"
            f"Please vouch in <#{VOUCH_CHANNEL_ID}> within **5 minutes**.\n\n"
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

    await ctx.reply(
        "✅ **Account generated!** Check your Direct Messages.",
        mention_author=False,
    )

    # Wait for this user to post the exact required vouch message.
    # Only a message in the configured vouch channel counts.
    def check_vouch(message: discord.Message):
        return (
            message.author.id == user_id
            and message.channel.id == VOUCH_CHANNEL_ID
            and not message.author.bot
            and message.content.strip() == VOUCH_MESSAGE
        )

    try:
        await bot.wait_for("message", check=check_vouch, timeout=300.0)
    except asyncio.TimeoutError:
        cooldowns[user_id] = datetime.utcnow() + timedelta(hours=2)
        try:
            await ctx.author.send(
                f"⚠️ You did not vouch in <#{VOUCH_CHANNEL_ID}> within "
                "5 minutes. Generator access is locked for **2 hours**."
            )
        except discord.Forbidden:
            pass


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
            "❌ Missing arguments. Correct usage: `.genaccess <vanity> <@role>`\n"
            "Example: `.genaccess .gg/V2NSJUb89P @FreeNFA`",
            mention_author=False,
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(
            "❌ I couldn't find that role. Mention the actual role, including "
            "roles with spaces in their names.\n"
            "Example: `.genaccess .gg/V2NSJUb89P @Free NFA Generator`",
            mention_author=False,
        )
    else:
        print(f".genaccess error: {error}")
        await ctx.reply(
            "❌ The command failed. Check the bot logs.",
            mention_author=False,
        )


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
