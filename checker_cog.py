import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio

class AccountChecker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def verify_minecraft_account(self, email: str, password: str):
        # Placeholder verification delay
        await asyncio.sleep(0.5)
        hypixel_status = "🟢 Unbanned"
        donut_status = "🟢 Unbanned"
        return hypixel_status, donut_status

    @app_commands.command(name="check", description="Check MC accounts from a combo file.")
    @app_commands.describe(
        file_path="The exact local path or filename of the email:pass file",
        channel="The channel where you want the embeds to be sent"
    )
    async def check_accounts(self, interaction: discord.Interaction, file_path: str, channel: discord.TextChannel):
        await interaction.response.send_message(f"🔄 Reading file: `{file_path}`...", ephemeral=True)

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
            await interaction.followup.send("❌ No valid `email:password` formatting found.", ephemeral=True)
            return

        await interaction.followup.send(f"🔎 Found {len(valid_combos)} accounts. Processing...", ephemeral=True)

        for email, password in valid_combos:
            hypixel, donut = await self.verify_minecraft_account(email, password)

            embed = discord.Embed(title="Minecraft Account Status", color=discord.Color.blue())
            embed.add_field(name="📧 Email", value=f"`{email}`", inline=False)
            embed.add_field(name="🔑 Password", value=f"`{password}`", inline=False)
            embed.add_field(name="🏰 Hypixel Status", value=hypixel, inline=True)
            embed.add_field(name="🍩 Donut SMP Status", value=donut, inline=True)

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                await interaction.followup.send(f"⚠️ Missing channel permissions.", ephemeral=True)
                break
            
            await asyncio.sleep(1)

        await interaction.followup.send("✅ Finished checking accounts!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AccountChecker(bot))
