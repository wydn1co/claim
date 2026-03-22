import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define intents
intents = discord.Intents.default()
intents.members = True  # Required for role assignment
# Message content intent not strictly needed for slash commands, 
# but good for general functionality if needed.
intents.message_content = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # This is where we sync the slash commands
        print("Syncing slash commands...")
        await self.tree.sync()
        print("Slash commands synced!")

bot = MyBot()

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

@bot.tree.command(name='setrole', description='Set the role to be given upon claiming (Admin only)')
@app_commands.describe(role='The role to assign to users who claim a valid key')
@app_commands.checks.has_permissions(administrator=True)
async def set_role(interaction: discord.Interaction, role: discord.Role):
    """Admin command to set the role to be given upon claiming."""
    config = load_config()
    config['role_id'] = role.id
    save_config(config)
    await interaction.response.send_message(f'Success! The role to be assigned has been set to: **{role.name}**', ephemeral=True)

@bot.tree.command(name='addkeys', description='Add one or more keys to the system (Admin only)')
@app_commands.describe(keys_str='Keys separated by spaces, commas, or newlines')
@app_commands.checks.has_permissions(administrator=True)
async def add_keys(interaction: discord.Interaction, keys_str: str):
    """Admin command to add one or more keys to the system."""
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

@bot.tree.command(name='claim', description='Claim the set role using a valid key')
@app_commands.describe(key='The valid key you want to use')
async def claim(interaction: discord.Interaction, key: str):
    """User command to claim the set role using a valid key."""
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
            await interaction.response.send_message(f'An unexpected error occurred: {str(e)}', ephemeral=True)
    else:
        await interaction.response.send_message('Invalid key. Please check your key and try again.', ephemeral=True)

# Global error handler for slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message('You do not have permission to use this command (Administrator required).', ephemeral=True)
    else:
        print(f"Unhandled error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"An error occurred: {str(error)}", ephemeral=True)

if __name__ == '__main__':
    if not TOKEN:
        print('Error: DISCORD_TOKEN not found in environment. Please set it in .env file.')
    else:
        bot.run(TOKEN)
