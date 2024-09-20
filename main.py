import os
import nextcord
from nextcord.ext import commands, tasks
from googleapiclient.discovery import build

# Initialize the bot with nextcord
intents = nextcord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# YouTube API setup
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # Fetch from environment variables
if not YOUTUBE_API_KEY:
    print("Error: YOUTUBE_API_KEY is missing!")
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Dictionary to store a list of channels to track for each guild
tracked_channels = {}

# Function to fetch the name of a YouTube channel from its ID
def get_channel_name(channel_id):
    try:
        # Use the YouTube API to get channel details
        request = youtube.channels().list(
            part="snippet",
            id=channel_id
        )
        response = request.execute()

        if 'items' in response and len(response['items']) > 0:
            channel_name = response['items'][0]['snippet']['title']
            return channel_name
        else:
            return None
    except Exception as e:
        print(f"Error fetching channel name: {e}")
        return None

# Slash command to set multiple YouTube channels to track
@bot.slash_command(name="add_channel", description="Add a YouTube channel to track for live streams.")
async def add_channel(interaction: nextcord.Interaction, channel_id: str):
    guild_id = interaction.guild.id

    # Initialize the channel list for the guild if it doesn't exist
    if guild_id not in tracked_channels:
        tracked_channels[guild_id] = []

    # Add the channel ID to the tracked channels for this guild, if it's not already added
    if channel_id not in tracked_channels[guild_id]:
        channel_name = get_channel_name(channel_id)
        
        if channel_name:
            tracked_channels[guild_id].append(channel_id)
            await interaction.response.send_message(f"Now tracking YouTube channel: {channel_name}")
            print(f"Tracking channel {channel_name} (ID: {channel_id}) for guild {guild_id}")
        else:
            await interaction.response.send_message("Error: Unable to retrieve the channel name. Please check the channel ID.")
    else:
        await interaction.response.send_message(f"Channel {channel_id} is already being tracked.")

# Slash command to remove a YouTube channel from the list
@bot.slash_command(name="remove_channel", description="Remove a YouTube channel from tracking.")
async def remove_channel(interaction: nextcord.Interaction, channel_id: str):
    guild_id = interaction.guild.id

    # Check if the guild is tracking channels
    if guild_id in tracked_channels and channel_id in tracked_channels[guild_id]:
        tracked_channels[guild_id].remove(channel_id)
        await interaction.response.send_message(f"Removed YouTube channel: {channel_id}")
        print(f"Removed channel {channel_id} for guild {guild_id}")
    else:
        await interaction.response.send_message(f"Channel {channel_id} is not being tracked.")

# Slash command to list all tracked channels for the guild
@bot.slash_command(name="list_channels", description="List all YouTube channels being tracked.")
async def list_channels(interaction: nextcord.Interaction):
    guild_id = interaction.guild.id

    # List the tracked channels for the guild
    if guild_id in tracked_channels and len(tracked_channels[guild_id]) > 0:
        channels = "\n".join(tracked_channels[guild_id])
        await interaction.response.send_message(f"Currently tracking these channels:\n{channels}")
    else:
        await interaction.response.send_message("No channels are currently being tracked.")

# Function to check if any of the YouTube channels are live
def check_live_stream(channel_id):
    try:
        # Search for live streams in the channel using YouTube API
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            eventType="live",
            type="video",
            maxResults=1  # Only get the most recent live stream
        )
        response = request.execute()

        # Debugging: print the API response to the console
        print(f"Response from YouTube API for channel {channel_id}: {response}")

        # If live stream exists, return the relevant information
        if 'items' in response and len(response['items']) > 0:
            stream = response['items'][0]
            stream_title = stream['snippet']['title']
            stream_thumbnail = stream['snippet']['thumbnails']['high']['url']
            stream_url = f"https://www.youtube.com/watch?v={stream['id']['videoId']}"
            return (True, stream_title, stream_thumbnail, stream_url)

    except Exception as e:
        print(f"Error fetching live stream data: {e}")

    return (False, None, None, None)

# Task to check for live streams periodically for multiple channels
@tasks.loop(minutes=5)
async def check_streams():
    print("Checking streams...")
    for guild_id, channels in tracked_channels.items():
        for channel_id in channels:
            print(f"Checking channel {channel_id} for guild {guild_id}")
            is_live, stream_title, stream_thumbnail, stream_url = check_live_stream(channel_id)

            guild = bot.get_guild(guild_id)
            if guild and is_live:
                print(f"Channel {channel_id} is live with title: {stream_title}")
                # Create an embed message for the live stream
                embed = nextcord.Embed(
                    title=f"{stream_title} is live!",
                    description=f"[Click to watch the stream]({stream_url})",
                    color=nextcord.Color.red()
                )
                embed.set_image(url=stream_thumbnail)

                # Send the notification to the first text channel in the guild
                channel = guild.text_channels[0]  # Or specify a particular channel if needed
                await channel.send(content="@everyone", embed=embed)

# Ping command to test if the bot and slash commands are working
@bot.slash_command(name="ping", description="Ping the bot to check if it's online.")
async def ping(interaction: nextcord.Interaction):
    await interaction.response.send_message("Pong!")

# Sync the slash commands and start the task after the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    # Set Rich Presence (watching status)
    await bot.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.watching, name="YouTube streams"))

    # Sync the slash commands with Discord
    try:
        await bot.sync_application_commands()  # Ensure commands are registered
    except Exception as e:
        print(f"Error syncing slash commands: {e}")
    
    # Start checking for live streams
    check_streams.start()

# Run the bot
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not DISCORD_BOT_TOKEN:
    print("Error: DISCORD_BOT_TOKEN is missing!")
else:
    bot.run(DISCORD_BOT_TOKEN)
