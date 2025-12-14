import discord
from discord.ext import commands
import google.generativeai as genai
import os
import aiohttp
import json
import random
import urllib.parse
from keep_alive import keep_alive

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- SAFETY SETTINGS (UNFILTERED) ---
# This allows the bot to answer almost anything without getting blocked.
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# --- SYSTEM PROMPT (SPEED) ---
# Instructions to make the bot answer fast and short.
SYSTEM_PROMPT = "You are a helpful assistant. Give concise, direct, and detailed answers. Avoid filler words. Be precise."

# --- SMART MODEL SETUP ---
genai.configure(api_key=GEMINI_API_KEY)

def get_model():
    # Try 1: Fast Model (Flash)
    try:
        print("🔌 Attempting to connect to Gemini 1.5 Flash...")
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_PROMPT, safety_settings=safety_settings)
        # Test the connection immediately
        model.generate_content("test") 
        print("✅ Success! Using Fast Brain.")
        return model
    except Exception as e:
        # Try 2: Standard Model (Pro) - The Fallback
        print(f"⚠️ Flash failed ({e}). Switching to Standard Brain.")
        return genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)

model = get_model()
bot_settings = {}

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- HELPER FUNCTIONS ---
async def check_channel(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id in bot_settings and "allowed_channel" in bot_settings[guild_id]:
        if ctx.channel.id != bot_settings[guild_id]["allowed_channel"]:
            return False
    return True

async def log_usage(ctx, command, content):
    guild_id = str(ctx.guild.id)
    if guild_id in bot_settings and "log_channel" in bot_settings[guild_id]:
        channel = bot.get_channel(bot_settings[guild_id]["log_channel"])
        if channel:
            embed = discord.Embed(title=f"🚀 Log: ${command}", color=discord.Color.teal())
            embed.add_field(name="User", value=f"{ctx.author.name}")
            embed.add_field(name="Input", value=content[:500])
            await channel.send(embed=embed)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'⚡ Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

# --- COMMANDS ---
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="⚡ Bot Commands", color=0xFFD700)
    embed.add_field(name="AI", value="`$ask`\n`$explain`\n`$summary`", inline=True)
    embed.add_field(name="Fun", value="`$imagine`", inline=True)
    embed.add_field(name="Admin", value="`$setchannel`\n`$setlogs`", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"⚡ Latency: `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    # This will tell you exactly which brain is running
    try:
        if "flash" in model.model_name:
            brain = "Gemini Flash (Fast)"
        else:
            brain = "Gemini Pro (Stable)"
    except:
        brain = "Gemini Pro (Fallback)"
        
    await ctx.send(f"🟢 **Online** | Brain: `{brain}`")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    if not await check_channel(ctx): return

    async with ctx.typing():
        try:
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                if not attachment.content_type.startswith('image/'):
                    await ctx.send("❌ Image only.")
                    return
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        image_data = await resp.read()
                        content = [{"mime_type": attachment.content_type, "data": image_data}, prompt if prompt else "Analyze this."]
                        response = model.generate_content(content)
                        await ctx.send(response.text[:2000])
            else:
                if not prompt: await ctx.send("Usage: `$ask [question]`"); return
                response = model.generate_content(prompt)
                await ctx.send(response.text[:2000])
            
            await log_usage(ctx, "ask", prompt)
        except Exception as e:
            await ctx.send(f"⚠️ Answer Error: {e}")

@bot.command(name="explain")
async def explain(ctx, *, topic: str):
    if not await check_channel(ctx): return
    async with ctx.typing():
        response = model.generate_content(f"Explain '{topic}' in 2-3 short sentences. Be simple.")
        await ctx.send(f"🎓 **{topic}:**\n{response.text}")

@bot.command(name="summary")
async def summary(ctx, *, text: str):
    if not await check_channel(ctx): return
    async with ctx.typing():
        response = model.generate_content(f"Summarize this in 3 bullet points:\n{text}")
        await ctx.send(f"📝 **Summary:**\n{response.text}")

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    if not await check_channel(ctx): return

    async with ctx.typing():
        try:
            clean_prompt = urllib.parse.quote(prompt)
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            
            embed = discord.Embed(title=f"🎨 Generated", color=discord.Color.purple())
            embed.set_image(url=url)
            embed.set_footer(text=f"Prompt: {prompt[:50]}...")
            await ctx.send(embed=embed)
            await log_usage(ctx, "imagine", prompt)

        except Exception as e:
            await ctx.send(f"❌ Image Failed: {e}")

# --- ADMIN ---
@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in bot_settings: bot_settings[guild_id] = {}
    bot_settings[guild_id]["allowed_channel"] = ctx.channel.id
    await ctx.send(f"🔒 Locked to {ctx.channel.mention}")

@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def setlogs(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in bot_settings: bot_settings[guild_id] = {}
    bot_settings[guild_id]["log_channel"] = ctx.channel.id
    await ctx.send(f"📄 Logs set to {ctx.channel.mention}")

keep_alive()
bot.run(DISCORD_TOKEN)
