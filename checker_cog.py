import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio

class AccountChecker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def verify_minecraft_account(self, email: str, password: str):
        # Simulated verification logic placeholder
        await asyncio.sleep(0.3)
        hypixel_status = "🟢 Unbanned"
        donut_status = "🟢 Unbanned"
        return hypixel_status, donut_status

    @app_commands.command(name="check", description="Check MC accounts from a file and send them in a single bulk summary.")
    @app_commands.describe(
        file_path="The exact local path or filename of the email:pass file",
        channel="The channel where you want the single embed to be sent"
    )
    async def check_accounts(self, interaction: discord.Interaction, file_path: str, channel: discord.TextChannel):
        await interaction.response.send_message(f"🔄 Processing combo file: `{file_path}`...", ephemeral=True)

        if not os.path.exists(file_path):
            await interaction.followup.send(f"❌ Error: File `{file_path}` not found.", ephemeral=True)
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception as e:
            await interaction.followup.send(f"❌ Error reading file: {str(e)}", ephemeral=True)
            return

        valid_combos = []
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                valid_combos.append((parts[0].strip(), parts[1].strip()))

        if not valid_combos:
            await interaction.followup.send("❌ No valid `email:password` lines found.", ephemeral=True)
            return

        await interaction.followup.send(f"🔎 Found {len(valid_combos)} accounts. Running check...", ephemeral=True)

        # Create one overarching master embed
        bulk_embed = discord.Embed(
            title="📊 Minecraft Account Status Batch Report",
            description=f"Total accounts checked: **{len(valid_combos)}**",
            color=discord.Color.green()
        )

        for email, password in valid_combos:
            hypixel, donut = await self.verify_minecraft_account(email, password)
            
            # Format each account nicely as a compact field entry
            field_value = f"🔑 Pass: `{password}`\n🏰 Hypixel: {hypixel} | 🍩 Donut: {donut}"
            bulk_embed.add_field(name=f"📧 {email}", value=field_value, inline=False)

        # Send everything grouped into one single delivery message
        try:
            await channel.send(embed=bulk_embed)
            await interaction.followup.send("✅ Bulk report sent successfully!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Missing channel permissions in {channel.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AccountChecker(bot))
