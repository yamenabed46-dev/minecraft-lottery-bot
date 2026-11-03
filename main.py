import os
import sqlite3
import random
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup Intents & Bot Instance
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------------------------------------------
# Database Initialization (SQLite)
# -------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("lottery.db")
    cursor = conn.cursor()
    
    # Table for active lottery entries
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            tickets INTEGER DEFAULT 1
        )
    """)
    
    # Table for system configuration
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect("lottery.db")

# -------------------------------------------------------------------
# Bot Events & Slash Command Sync
# -------------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
        
    if not auto_lottery_draw.is_running():
        auto_lottery_draw.start()

# -------------------------------------------------------------------
# Slash Commands
# -------------------------------------------------------------------
@bot.tree.command(name="buyticket", description="Enter the Minecraft Lifesteal lottery!")
@app_commands.describe(tickets="Number of tickets to buy (Default: 1)")
async def buyticket(interaction: discord.Interaction, tickets: int = 1):
    if tickets < 1:
        await interaction.response.send_message("You must enter at least 1 ticket!", ephemeral=True)
        return

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT tickets FROM entries WHERE user_id = ?", (interaction.user.id,))
    row = cursor.fetchone()
    
    if row:
        new_total = row[0] + tickets
        cursor.execute("UPDATE entries SET tickets = ? WHERE user_id = ?", (new_total, interaction.user.id))
    else:
        new_total = tickets
        cursor.execute("INSERT INTO entries (user_id, username, tickets) VALUES (?, ?, ?)", 
                       (interaction.user.id, str(interaction.user), tickets))
        
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="🎟️ Lottery Entry Confirmed!",
        description=f"Added **{tickets}** ticket(s) for {interaction.user.mention}.",
        color=discord.Color.green()
    )
    embed.add_field(name="Total Tickets Held", value=str(new_total), inline=True)
    embed.set_footer(text="Minecraft Lifesteal Server Lottery")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="entries", description="View total tickets entered in the current lottery.")
async def entries(interaction: discord.Interaction):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT SUM(tickets), COUNT(user_id) FROM entries")
    total_tickets, total_players = cursor.fetchone()
    conn.close()

    total_tickets = total_tickets or 0
    total_players = total_players or 0

    embed = discord.Embed(
        title="📊 Current Lottery Pool",
        color=discord.Color.blue()
    )
    embed.add_field(name="Total Tickets", value=str(total_tickets), inline=True)
    embed.add_field(name="Total Participants", value=str(total_players), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="draw", description="Force draw the lottery winner (Admins only).")
@app_commands.checks.has_permissions(administrator=True)
async def draw(interaction: discord.Interaction):
    await interaction.response.defer()
    winner_embed = await run_lottery_draw()
    await interaction.followup.send(embed=winner_embed)

@draw.error
async def draw_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You need Administrator permissions to force draw the lottery.", ephemeral=True)

@bot.tree.command(name="setannouncechannel", description="Set the channel where lottery winners are announced.")
@app_commands.checks.has_permissions(administrator=True)
async def setannouncechannel(interaction: discord.Interaction, channel: discord.TextChannel):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('announce_channel', ?)", (str(channel.id),))
    conn.commit()
    conn.close()
    
    await interaction.response.send_message(f"Lottery announcements channel set to {channel.mention}.")

# -------------------------------------------------------------------
# Lottery Drawing Logic & Background Task
# -------------------------------------------------------------------
async def run_lottery_draw() -> discord.Embed:
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT user_id, username, tickets FROM entries")
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        return discord.Embed(
            title="🎰 Lottery Draw",
            description="No tickets were purchased for this drawing!",
            color=discord.Color.red()
        )
        
    # Weighted random selection based on ticket count
    pool = []
    total_tickets = 0
    for uid, name, tcount in rows:
        pool.extend([uid] * tcount)
        total_tickets += tcount

    winner_id = random.choice(pool)
    
    # Reset pool
    cursor.execute("DELETE FROM entries")
    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="🎉 LOTTERY WINNER DRAWN! 🎉",
        description=f"Congratulations to <@{winner_id}> for winning the Lifesteal Lottery!",
        color=discord.Color.gold()
    )
    embed.add_field(name="Total Pool Tickets", value=str(total_tickets), inline=True)
    embed.set_footer(text=f"Drawn on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    return embed

@tasks.loop(hours=24)
async def auto_lottery_draw():
    """Automated daily drawing task."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = 'announce_channel'")
    row = cursor.fetchone()
    conn.close()

    if row:
        channel_id = int(row[0])
        channel = bot.get_channel(channel_id)
        if channel:
            embed = await run_lottery_draw()
            await channel.send(embed=embed)

@auto_lottery_draw.before_loop
async def before_auto_draw():
    await bot.wait_until_ready()

# -------------------------------------------------------------------
# Run Bot
# -------------------------------------------------------------------
if __name__ == "__main__":
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN environment variable is missing!")
    bot.run(TOKEN)
