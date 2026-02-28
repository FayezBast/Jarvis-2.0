"""
Discord Bot Integration for Jarvis-2.0

Alternative to Telegram - uses Discord for remote control.

Setup:
1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to Bot section, create bot, copy token
4. Enable MESSAGE CONTENT INTENT in Bot settings
5. Add DISCORD_BOT_TOKEN to .env
6. Invite bot to your server with proper permissions
"""

import os
import sys
import logging
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("❌ discord.py not installed!")
    print("Run: pip install discord.py")
    sys.exit(1)

from dotenv import load_dotenv
from core.agent import create_agent
from config import get_config
from prompts import system_prompt

load_dotenv()


class JarvisBot(commands.Bot):
    """Discord bot for Jarvis."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Jarvis - Your Local-First AI Assistant"
        )
        
        self.config = get_config()
        self.agent = None
        self.authorized_users = self._load_authorized_users()
    
    def _load_authorized_users(self) -> set:
        """Load authorized Discord user IDs."""
        users = os.getenv("DISCORD_AUTHORIZED_USERS", "")
        if users:
            return set(int(u.strip()) for u in users.split(",") if u.strip())
        return set()
    
    def _get_agent(self):
        """Get or create agent."""
        if self.agent is None:
            provider = self.config.provider
            model_name = self.config.model_name if provider == "gemini" else self.config.ollama_model
            self.agent = create_agent(
                api_key=self.config.gemini_api_key if provider == "gemini" else None,
                system_prompt=system_prompt,
                working_directory=os.getenv("JARVIS_WORKING_DIR", os.getcwd()),
                model_name=model_name,
                dry_run=os.getenv("JARVIS_DRY_RUN", "false").lower() == "true",
                verbose=False,
                provider=provider,
                base_url=self.config.ollama_base_url,
                local_tools_enabled=self.config.local_tools_enabled,
                max_iterations=self.config.max_iterations,
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay,
                temperature=self.config.temperature,
            )
        return self.agent
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        if not self.authorized_users:
            return True
        return user_id in self.authorized_users
    
    async def on_ready(self):
        """Called when bot is ready."""
        print(f"✅ Logged in as {self.user.name} ({self.user.id})")
        print(f"   Invite URL: https://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=274877958144&scope=bot")
        print()
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="your commands | !help"
            )
        )
    
    async def on_message(self, message: discord.Message):
        """Handle messages."""
        # Ignore own messages
        if message.author == self.user:
            return
        
        # Process commands first
        await self.process_commands(message)
        
        # Check for DM or mention
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user in message.mentions
        
        if not (is_dm or is_mentioned):
            return
        
        # Auth check
        if not self.is_authorized(message.author.id):
            await message.reply(f"⛔ Unauthorized. Your ID: {message.author.id}")
            return
        
        # Get message content (remove mention if present)
        content = message.content.replace(f"<@{self.user.id}>", "").strip()
        if not content:
            return
        
        # Show typing
        async with message.channel.typing():
            try:
                agent = self._get_agent()
                
                # Run in executor
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, agent.process, content)
                
                # Split long messages (Discord limit is 2000 chars)
                if len(response) > 1900:
                    chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                    for chunk in chunks:
                        await message.reply(f"```\n{chunk}\n```")
                else:
                    await message.reply(response)
                    
            except Exception as e:
                logger.exception("Error processing message")
                await message.reply(f"❌ Error: {str(e)[:200]}")


# Create bot instance
bot = JarvisBot()


@bot.command(name="status")
async def status(ctx):
    """Show system status."""
    if not bot.is_authorized(ctx.author.id):
        return
    
    import platform
    import shutil
    
    total, used, free = shutil.disk_usage("/")
    disk_percent = (used / total) * 100
    
    embed = discord.Embed(title="🖥️ System Status", color=0x00ff00)
    embed.add_field(name="OS", value=f"{platform.system()} {platform.release()}", inline=True)
    embed.add_field(name="Python", value=platform.python_version(), inline=True)
    embed.add_field(name="Disk", value=f"{disk_percent:.1f}% ({free // (1024**3)} GB free)", inline=True)
    embed.add_field(name="Working Dir", value=f"`{os.getcwd()}`", inline=False)
    embed.add_field(name="Agent", value="✅ Active" if bot.agent else "💤 Idle", inline=True)
    
    await ctx.send(embed=embed)


@bot.command(name="reset")
async def reset(ctx):
    """Reset conversation."""
    if not bot.is_authorized(ctx.author.id):
        return
    
    if bot.agent:
        bot.agent.reset()
    await ctx.send("🗑️ Conversation reset!")


@bot.command(name="jarvis")
async def jarvis_cmd(ctx, *, query: str):
    """Send a command to Jarvis."""
    if not bot.is_authorized(ctx.author.id):
        await ctx.send(f"⛔ Unauthorized. Your ID: {ctx.author.id}")
        return
    
    async with ctx.typing():
        try:
            agent = bot._get_agent()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent.process, query)
            
            if len(response) > 1900:
                chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                for chunk in chunks:
                    await ctx.send(f"```\n{chunk}\n```")
            else:
                await ctx.send(response)
                
        except Exception as e:
            await ctx.send(f"❌ Error: {str(e)[:200]}")


def main():
    """Start the Discord bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not token:
        print("❌ DISCORD_BOT_TOKEN not found in .env!")
        print("\nTo set up:")
        print("1. Go to https://discord.com/developers/applications")
        print("2. Create new application → Bot → Copy token")
        print("3. Enable MESSAGE CONTENT INTENT")
        print("4. Add to .env:")
        print("   DISCORD_BOT_TOKEN=your_token_here")
        print("\nOptional - restrict access:")
        print("   DISCORD_AUTHORIZED_USERS=123456789,987654321")
        sys.exit(1)
    
    print("🤖 Starting Jarvis Discord Bot...")
    bot.run(token)


if __name__ == "__main__":
    main()
