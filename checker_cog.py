import discord
from discord import app_commands
from discord.ext import commands
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

    @app_commands.command(name="check", description="Upload a .txt combo file to check Minecraft account ban status.")
    @app_commands.describe(
        file="Upload your account .txt file formatted as email:password",
        channel="The target channel where you want the summary embed sent"
    )
    async def check_accounts(self, interaction: discord.Interaction, file: discord.Attachment, channel: discord.TextChannel):
        # Validate that the user actually uploaded a text file
        if not file.filename.endswith('.txt'):
            await interaction.response.send_message("❌ Error: Please upload a valid text file ending in `.txt`.", ephemeral=True)
            return

        # Acknowledge interaction right away to prevent application timeout
        await interaction.response.send_message(f"📥 Downloading and processing `{file.filename}`...", ephemeral=True)

        try:
            # Read the attachment bytes directly from Discord's CDN into memory
            file_bytes = await file.read()
            content = file_bytes.decode('utf-8')
            lines = content.splitlines()
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to parse uploaded file: {str(e)}", ephemeral=True)
            return

        valid_combos = []
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                valid_combos.append((parts[0].strip(), parts[1].strip()))

        if not valid_combos:
            await interaction.followup.send("❌ No valid accounts found. Ensure formatting is `email:password` on each line.", ephemeral=True)
            return

        await interaction.followup.send(f"🔎 Found {len(valid_combos)} accounts. Executing status checks...", ephemeral=True)

        # Build a single master delivery summary card
        bulk_embed = discord.Embed(
            title="📊 Minecraft Account Status Batch Report",
            description=f"Total accounts processed: **{len(valid_combos)}**",
            color=discord.Color.green()
        )

        for email, password in valid_combos:
            hypixel, donut = await self.verify_minecraft_account(email, password)
            
            # Format entries in a sleek inline profile block
            field_value = f"🔑 Pass: `{password}`\n🏰 Hypixel: {hypixel} | 🍩 Donut: {donut}"
            bulk_embed.add_field(name=f"📧 {email}", value=field_value, inline=False)

        try:
            await channel.send(embed=bulk_embed)
            await interaction.followup.send("✅ Bulk report sent to the designated channel successfully!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"⚠️ Bot lacks permissions to send messages into {channel.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AccountChecker(bot))
