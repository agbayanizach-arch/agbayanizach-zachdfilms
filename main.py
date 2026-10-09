import os
import re
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
    command_prefix=PREFIX,
    intents=intents,
    help_command=None,
)

# Dynamic state (stored in memory; resets when the process restarts).
current_vanity = "your-vanity-here"
target_role_id = None
account_stock = []


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
