import os
import json
import discord
import logging
import time
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from typing import Optional, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('discord_bot')

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '.')

# Define intents
intents = discord.Intents.default()
intents.members = True  # Required for role assignment
intents.message_content = True # Required for prefix commands

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents)

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
    logger.info(f'Prefix is: {PREFIX}')
    logger.info('------')

# Helper logic for commands to avoid duplication
async def process_setrole(target: Union[discord.Interaction, commands.Context], role: discord.Role):
    try:
        config = load_config()
        config['role_id'] = role.id
        save_config(config)
        msg = f'Success! The role to be assigned has been set to: **{role.name}**'
        if isinstance(target, discord.Interaction):
            await target.response.send_message(msg, ephemeral=True)
        else:
            await target.send(msg)
    except Exception as e:
        logger.error(f"Error in set_role logic: {e}")
        error_msg = "An error occurred while setting the role."
        if isinstance(target, discord.Interaction):
            await target.response.send_message(error_msg, ephemeral=True)
        else:
            await target.send(error_msg)

async def process_addkeys(target: Union[discord.Interaction, commands.Context], keys_str: str):
    try:
        normalized_keys = keys_str.replace(',', ' ').replace('\n', ' ')
        keys = [k.strip() for k in normalized_keys.split() if k.strip()]
        
        if not keys:
            msg = 'Please provide at least one key to add.'
            if isinstance(target, discord.Interaction):
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.send(msg)
            return

        config = load_config()
        existing_keys = set(config.get('keys', []))
        new_keys = [k for k in keys if k not in existing_keys]
        
        if not new_keys:
            msg = 'All provided keys are already in the system.'
            if isinstance(target, discord.Interaction):
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.send(msg)
            return

        config['keys'] = list(existing_keys.union(set(new_keys)))
        save_config(config)
        msg = f'Successfully added {len(new_keys)} new key(s).'
        if isinstance(target, discord.Interaction):
            await target.response.send_message(msg, ephemeral=True)
        else:
            await target.send(msg)
    except Exception as e:
        logger.error(f"Error in add_keys logic: {e}")
        error_msg = "An error occurred while adding keys."
        if isinstance(target, discord.Interaction):
            await target.response.send_message(error_msg, ephemeral=True)
        else:
            await target.send(error_msg)

async def process_claim(target: Union[discord.Interaction, commands.Context], key: str):
    try:
        config = load_config()
        keys = config.get('keys', [])
        role_id = config.get('role_id')
        
        user = target.user if isinstance(target, discord.Interaction) else target.author
        guild = target.guild

        if not role_id:
            msg = 'The claimable role has not been set by an administrator yet.'
            if isinstance(target, discord.Interaction):
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.send(msg)
            return

        if key in keys:
            role = guild.get_role(role_id)
            if not role:
                msg = 'Error: The configured role could not be found in this server.'
                if isinstance(target, discord.Interaction):
                    await target.response.send_message(msg, ephemeral=True)
                else:
                    await target.send(msg)
                return

            try:
                await user.add_roles(role)
                keys.remove(key)
                config['keys'] = keys
                save_config(config)
                msg = f'Congratulations! {user.mention}, you have been roled the the specified role.'
                if isinstance(target, discord.Interaction):
                    await target.response.send_message(msg)
                else:
                    await target.send(msg)
            except discord.Forbidden:
                msg = 'Error: I do not have permission to manage roles. Please check my permissions and hierarchy.'
                if isinstance(target, discord.Interaction):
                    await target.response.send_message(msg, ephemeral=True)
                else:
                    await target.send(msg)
            except Exception as e:
                logger.error(f"Failed to add role to user: {e}")
                msg = f'An unexpected error occurred: {str(e)}'
                if isinstance(target, discord.Interaction):
                    await target.response.send_message(msg, ephemeral=True)
                else:
                    await target.send(msg)
        else:
            msg = 'Invalid key. Please check your key and try again.'
            if isinstance(target, discord.Interaction):
                await target.response.send_message(msg, ephemeral=True)
            else:
                await target.send(msg)
    except Exception as e:
        logger.error(f"Error in claim logic: {e}")
        error_msg = "An error occurred while processing your claim."
        if isinstance(target, discord.Interaction):
            await target.response.send_message(error_msg, ephemeral=True)
        else:
            await target.send(error_msg)

# --- SLASH COMMANDS ---

@bot.tree.command(name='setrole', description='Set the role to be given upon claiming (Admin only)')
@app_commands.describe(role='The role to assign to users who claim a valid key')
@app_commands.checks.has_permissions(administrator=True)
async def set_role_slash(interaction: discord.Interaction, role: discord.Role):
    await process_setrole(interaction, role)

@bot.tree.command(name='addkeys', description='Add one or more keys to the system (Admin only)')
@app_commands.describe(keys_str='Keys separated by spaces, commas, or newlines')
@app_commands.checks.has_permissions(administrator=True)
async def add_keys_slash(interaction: discord.Interaction, keys_str: str):
    await process_addkeys(interaction, keys_str)

@bot.tree.command(name='claim', description='Claim the set role using a valid key')
@app_commands.describe(key='The valid key you want to use')
async def claim_slash(interaction: discord.Interaction, key: str):
    await process_claim(interaction, key)

# --- PREFIX COMMANDS ---

@bot.command(name='setrole')
@commands.has_permissions(administrator=True)
async def set_role_prefix(ctx, role: discord.Role):
    await process_setrole(ctx, role)

@bot.command(name='addkeys')
@commands.has_permissions(administrator=True)
async def add_keys_prefix(ctx, *, keys_str: str):
    await process_addkeys(ctx, keys_str)

@bot.command(name='claim')
async def claim_prefix(ctx, key: str):
    await process_claim(ctx, key)

# --- ERROR HANDLERS ---

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message('You do not have permission to use this command (Administrator required).', ephemeral=True)
    else:
        logger.error(f"Unhandled app command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"An error occurred: {str(error)}", ephemeral=True)

@set_role_prefix.error
@add_keys_prefix.error
async def prefix_admin_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('You do not have permission to use this command (Administrator required).')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'Usage: {PREFIX}{ctx.command.name} <argument>')
    elif isinstance(error, commands.BadArgument):
        await ctx.send('Invalid argument. Please check your input.')

@claim_prefix.error
async def prefix_claim_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'Usage: {PREFIX}claim <key>')

if __name__ == '__main__':
    if not TOKEN:
        logger.critical('DISCORD_TOKEN not found in environment. Please check your .env file or environment variables.')
    else:
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Starting bot (Attempt {retry_count + 1})...")
                bot.run(TOKEN)
                break
            except discord.LoginFailure:
                logger.critical("Invalid Discord Token provided. Please check your .env file.")
                break
            except Exception as e:
                retry_count += 1
                wait_time = min(60, 2 ** retry_count)
                logger.error(f"Bot crashed with error: {e}")
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        if retry_count >= max_retries:
            logger.critical("Maximum retries reached. Container will now exit.")
