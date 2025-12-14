import discord
from discord.ext import commands
import google.generativeai as genai
import os
import aiohttp
import json
from keep_alive import keep_alive

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SETTINGS_FILE = "settings.json"

# --- SETUP GEMINI (Smart Selector) ---
genai.configure(api_key=GEMINI_API_KEY)

def get_model():
    try:
        print("🔍 Searching for available models...")
        supported_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                supported_models.append(m.name)
        
        # Priority list
        preferences = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']
        for pref in preferences:
            if pref in supported_models:
                print(f"✅ Auto-selected model: {pref}")
                return genai.GenerativeModel(pref)
        if supported_models:
             return genai.GenerativeModel(supported_models[0])
    except Exception as e:
        print(f"⚠️ Auto-detect failed: {e}. Falling back to 'gemini-pro'")
    return genai.GenerativeModel('gemini-pro')

model = get_model()

# --- SETTINGS MANAGEMENT ---
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

bot_settings = load_settings()

# --- SETUP DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
# CHANGED PREFIX TO $
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- HELPER FUNCTIONS ---
async def is_in_allowed_channel(ctx):
    # Checks if the command is used in the designated channel
    guild_id = str(ctx.guild.id)
    if guild_id in bot_settings and "allowed_channel" in bot_settings[guild_id]:
        allowed_channel_id = bot_settings[guild_id]["allowed_channel"]
        if ctx.channel.id != allowed_channel_id:
            # Optionally warn them, or just silently ignore
            # await ctx.send(f"❌ You can only use bot commands in <#{allowed_channel_id}>")
            return False
    return True

async def send_log(ctx, command_name, content):
    # Sends a log embed to the designated log channel
    guild_id = str(ctx.guild.id)
    if guild_id in bot_settings and "log_channel" in bot_settings[guild_id]:
        log_channel_id = bot_settings[guild_id]["log_channel"]
        log_channel = bot.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(title=f"📝 Command Used: ${command_name}", color=discord.Color.orange())
            embed.set_author(name=ctx.author.name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            embed.add_field(name="Channel", value=ctx.channel.mention, inline=True)
            embed.add_field(name="Content", value=content[:1000] if content else "Image Attachment", inline=False)
            embed.set_footer(text=f"User ID: {ctx.author.id}")
            await log_channel.send(embed=embed)

# --- EVENTS & GENERAL COMMANDS ---
@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} with prefix $')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="🤖 Bot Commands", color=0x3498db)
    embed.add_field(name="💬 AI & Images", value="`$ask [question]` - Ask AI anything\n`$imagine [prompt]` - Generate an image", inline=False)
    embed.add_field(name="⚙️ Utility", value="`$status` - Check bot health\n`$ping` - Check latency", inline=False)
    embed.add_field(name="🛡️ Admin Only", value="`$setchannel` - Restrict bot to current channel\n`$setlogs` - Set current channel for logs", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="status")
async def status(ctx):
    # Simple status check
    embed = discord.Embed(title="🟢 System Status", color=discord.Color.green())
    embed.add_field(name="Status", value="Online & Operational")
    embed.add_field(name="AI Model", value=f"`{model.model_name.split('/')[-1]}`")
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: `{latency}ms`")

# --- ADMIN SETUP COMMANDS ---
@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    # Sets the current channel as the ONLY place the bot works
    guild_id = str(ctx.guild.id)
    if guild_id not in bot_settings: bot_settings[guild_id] = {}
    
    bot_settings[guild_id]["allowed_channel"] = ctx.channel.id
    save_settings(bot_settings)
    await ctx.send(f"✅ Bot commands are now restricted to this channel: {ctx.channel.mention}")

@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def setlogs(ctx):
    # Sets the current channel as the log channel
    guild_id = str(ctx.guild.id)
    if guild_id not in bot_settings: bot_settings[guild_id] = {}
    
    bot_settings[guild_id]["log_channel"] = ctx.channel.id
    save_settings(bot_settings)
    await ctx.send(f"✅ Logging channel set to: {ctx.channel.mention}")

# --- AI COMMANDS ---
@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    # 1. Check Channel Restriction
    if not await is_in_allowed_channel(ctx): return

    async with ctx.typing():
        try:
            log_content = prompt
            response_text = ""
            
            # Handle Image Attachment + Text
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                if not attachment.content_type.startswith('image/'):
                    await ctx.send("Please attach a valid image (PNG/JPG).")
                    return
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status != 200: await ctx.send("Failed to download image."); return
                        image_data = await resp.read()
                        
                        image_parts = [{"mime_type": attachment.content_type, "data": image_data}]
                        prompt_text = prompt if prompt else "Describe this image."
                        response = model.generate_content([prompt_text, image_parts[0]])
                        response_text = response.text
            # Handle Text Only
            else:
                if not prompt: await ctx.send("Usage: `$ask [question]`"); return
                response = model.generate_content(prompt)
                response_text = response.text

            # Send Response (Split if long)
            if len(response_text) > 2000:
                await ctx.send(response_text[:2000])
                await ctx.send(response_text[2000:])
            else:
                await ctx.send(response_text)
            
            # 3. Log the command
            await send_log(ctx, "ask", log_content)

        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    # 1. Check Channel Restriction
    if not await is_in_allowed_channel(ctx): return
    
    async with ctx.typing():
        try:
            # Use free Pollinations API
            clean_prompt = prompt.replace(" ", "%20")
            image_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true"
            
            embed = discord.Embed(title=f"🎨 Generated: {prompt}", color=discord.Color.random())
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Requested by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            # 3. Log the command
            await send_log(ctx, "imagine", prompt)
            
        except Exception as e:
            await ctx.send(f"Could not generate image: {e}")

# --- ERROR HANDLING ---
@setchannel.error
@setlogs.error
async def admin_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need **Administrator** permission to use this setup command.")

keep_alive()
bot.run(DISCORD_TOKEN)
