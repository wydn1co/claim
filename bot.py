import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('PREFIX', '.')

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for role assignment

# Setup bot
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# File for storing keys and configuration
CONFIG_FILE = 'config.json'

def load_config():
    """Load configuration from the JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"keys": [], "role_id": None}

def save_config(config):
    """Save configuration to the JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

@bot.command(name='setrole')
@commands.has_permissions(administrator=True)
async def set_role(ctx, role: discord.Role):
    """Admin command to set the role to be given upon claiming."""
    config = load_config()
    config['role_id'] = role.id
    save_config(config)
    await ctx.send(f'Success! The role to be assigned has been set to: **{role.name}**')

@bot.command(name='addkeys')
@commands.has_permissions(administrator=True)
async def add_keys(ctx, *, keys_str: str):
    """Admin command to add one or more keys to the system (space, comma, or newline separated)."""
    # Replace commas and newlines with spaces to simplify splitting
    normalized_keys = keys_str.replace(',', ' ').replace('\n', ' ')
    keys = [k.strip() for k in normalized_keys.split() if k.strip()]
    
    if not keys:
        await ctx.send('Please provide at least one key to add.')
        return

    config = load_config()
    existing_keys = set(config.get('keys', []))
    new_keys = [k for k in keys if k not in existing_keys]
    
    if not new_keys:
        await ctx.send('All provided keys are already in the system.')
        return

    config['keys'] = list(existing_keys.union(set(new_keys)))
    save_config(config)
    await ctx.send(f'Successfully added {len(new_keys)} new key(s).')

@bot.command(name='claim')
async def claim(ctx, key: str):
    """User command to claim the set role using a valid key."""
    config = load_config()
    keys = config.get('keys', [])
    role_id = config.get('role_id')

    if not role_id:
        await ctx.send('The claimable role has not been set by an administrator yet.')
        return

    if key in keys:
        role = ctx.guild.get_role(role_id)
        if not role:
            await ctx.send('Error: The configured role could not be found in this server.')
            return

        try:
            await ctx.author.add_roles(role)
            # Remove the key after successful claim
            keys.remove(key)
            config['keys'] = keys
            save_config(config)
            await ctx.send(f'Congratulations! {ctx.author.mention}, you have been roled the the specified role.')
        except discord.Forbidden:
            await ctx.send('Error: I do not have permission to manage roles. Please check my permissions.')
        except Exception as e:
            await ctx.send(f'An unexpected error occurred: {str(e)}')
    else:
        await ctx.send('Invalid key. Please check your key and try again.')

@set_role.error
@add_keys.error
async def admin_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('You do not have permission to use this command (Administrator required).')
    elif isinstance(error, commands.MissingRequiredArgument):
        if ctx.command.name == 'setrole':
            await ctx.send(f'Usage: {PREFIX}setrole @role')
        elif ctx.command.name == 'addkeys':
            await ctx.send(f'Usage: {PREFIX}addkeys <key1> <key2> ... (separated by space, comma or newline)')
    elif isinstance(error, commands.BadArgument):
        await ctx.send('Invalid argument. Please provide a valid role mention or ID.')

@claim.error
async def claim_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'Usage: {PREFIX}claim <your_key>')

if __name__ == '__main__':
    if not TOKEN:
        print('Error: DISCORD_TOKEN not found in environment. Please set it in .env file.')
    else:
        bot.run(TOKEN)
