import os
import json
import discord
import logging
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('discord_bot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define intents
intents = discord.Intents.default()
intents.members = True  # Required for role assignment
intents.message_content = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        try:
            logger.info("Syncing slash commands...")
            await self.tree.sync()
            logger.info("Slash commands synced!")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

bot = MyBot()

# File for storing keys and configuration
CONFIG_FILE = 'config.json'

def load_config():
    """Load configuration from the JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to decode config file, starting fresh: {e}")
    
    # Default config if file doesn't exist or is corrupted
    default_config = {"keys": [], "role_id": None}
    save_config(default_config)
    return default_config

def save_config(config):
    """Save configuration to the JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    logger.info('------')

@bot.tree.command(name='setrole', description='Set the role to be given upon claiming (Admin only)')
@app_commands.describe(role='The role to assign to users who claim a valid key')
@app_commands.checks.has_permissions(administrator=True)
async def set_role(interaction: discord.Interaction, role: discord.Role):
    """Admin command to set the role to be given upon claiming."""
    try:
        config = load_config()
        config['role_id'] = role.id
        save_config(config)
        await interaction.response.send_message(f'Success! The role to be assigned has been set to: **{role.name}**', ephemeral=True)
    except Exception as e:
        logger.error(f"Error in set_role command: {e}")
        await interaction.response.send_message("An error occurred while setting the role.", ephemeral=True)

@bot.tree.command(name='addkeys', description='Add one or more keys to the system (Admin only)')
@app_commands.describe(keys_str='Keys separated by spaces, commas, or newlines')
@app_commands.checks.has_permissions(administrator=True)
async def add_keys(interaction: discord.Interaction, keys_str: str):
    """Admin command to add one or more keys to the system."""
    try:
        # Replace commas and newlines with spaces to simplify splitting
        normalized_keys = keys_str.replace(',', ' ').replace('\n', ' ')
        keys = [k.strip() for k in normalized_keys.split() if k.strip()]
        
        if not keys:
            await interaction.response.send_message('Please provide at least one key to add.', ephemeral=True)
            return

        config = load_config()
        existing_keys = set(config.get('keys', []))
        new_keys = [k for k in keys if k not in existing_keys]
        
        if not new_keys:
            await interaction.response.send_message('All provided keys are already in the system.', ephemeral=True)
            return

        config['keys'] = list(existing_keys.union(set(new_keys)))
        save_config(config)
        await interaction.response.send_message(f'Successfully added {len(new_keys)} new key(s).', ephemeral=True)
    except Exception as e:
        logger.error(f"Error in add_keys command: {e}")
        await interaction.response.send_message("An error occurred while adding keys.", ephemeral=True)

@bot.tree.command(name='claim', description='Claim the set role using a valid key')
@app_commands.describe(key='The valid key you want to use')
async def claim(interaction: discord.Interaction, key: str):
    """User command to claim the set role using a valid key."""
    try:
        config = load_config()
        keys = config.get('keys', [])
        role_id = config.get('role_id')

        if not role_id:
            await interaction.response.send_message('The claimable role has not been set by an administrator yet.', ephemeral=True)
            return

        if key in keys:
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message('Error: The configured role could not be found in this server.', ephemeral=True)
                return

            try:
                await interaction.user.add_roles(role)
                # Remove the key after successful claim
                keys.remove(key)
                config['keys'] = keys
                save_config(config)
                await interaction.response.send_message(f'Congratulations! {interaction.user.mention}, you have been roled the the specified role.')
            except discord.Forbidden:
                await interaction.response.send_message('Error: I do not have permission to manage roles. Please check my permissions and hierarchy.', ephemeral=True)
            except Exception as e:
                logger.error(f"Failed to add role to user: {e}")
                await interaction.response.send_message(f'An unexpected error occurred: {str(e)}', ephemeral=True)
        else:
            await interaction.response.send_message('Invalid key. Please check your key and try again.', ephemeral=True)
    except Exception as e:
        logger.error(f"Error in claim command: {e}")
        await interaction.response.send_message("An error occurred while processing your claim.", ephemeral=True)

# Global error handler for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message('You do not have permission to use this command (Administrator required).', ephemeral=True)
    else:
        logger.error(f"Unhandled app command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"An error occurred: {str(error)}", ephemeral=True)

if __name__ == '__main__':
    if not TOKEN:
        logger.critical('DISCORD_TOKEN not found in environment. Please check your .env file or environment variables.')
    else:
        import time
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Starting bot (Attempt {retry_count + 1})...")
                bot.run(TOKEN)
                # If bot.run() returns normally (e.g., bot.close()), we can stop retrying
                break
            except discord.LoginFailure:
                logger.critical("Invalid Discord Token provided. Please check your .env file.")
                break
            except Exception as e:
                retry_count += 1
                wait_time = min(60, 2 ** retry_count) # Exponential backoff up to 60s
                logger.error(f"Bot crashed with error: {e}")
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        if retry_count >= max_retries:
            logger.critical("Maximum retries reached. Container will now exit.")
