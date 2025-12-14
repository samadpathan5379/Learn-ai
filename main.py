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

# --- SETUP GEMINI (FAST & UNFILTERED) ---
genai.configure(api_key=GEMINI_API_KEY)

# 1. SYSTEM PROMPT: Forces brevity and directness.
SYSTEM_PROMPT = "You are a helpful assistant. Give concise, direct, and detailed answers. Avoid filler words. Be precise."

# 2. SAFETY SETTINGS: Disables filters to prevent blocked responses.
# WE ARE TURNING OFF THE SAFETY FILTERS SO IT ANSWERS EVERYTHING.
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

def get_model():
    try:
        # Use Flash for speed, with system prompt and NO safety filters.
        return genai.GenerativeModel(
            'gemini-1.5-flash',
            system_instruction=SYSTEM_PROMPT,
            safety_settings=safety_settings
        )
    except:
        # Fallback to Pro if Flash has a hiccup
        return genai.GenerativeModel(
            'gemini-pro',
            safety_settings=safety_settings
        )

model = get_model()
bot_settings = {}

# --- SETUP DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
# 🔴 STRICT PREFIX: Only '$' works.
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
    # This print confirms only ONE bot is running.
    print(f'⚡ SINGLE INSTANCE: Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help | Speed Mode"))

# --- COMMANDS ---
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="⚡ Speed Bot Commands", color=0xFFD700)
    embed.add_field(name="🚀 AI", value="`$ask` - Fast Answers\n`$explain` - Simple Explain\n`$summary` - Bullet Points", inline=True)
    embed.add_field(name="🎨 Art", value="`$imagine` - Generate Image (Long prompts supported)", inline=True)
    embed.add_field(name="⚙️ Admin", value="`$setchannel` - Lock Channel\n`$setlogs` - Set Logs", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    # If you see two replies to this, you still have two bots running.
    await ctx.send(f"⚡ Speed: `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    await ctx.send(f"🟢 **Online** | Brain: `Gemini Flash 1.5` (Unfiltered)")

# --- FAST AI COMMANDS ---
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
                # Generate with NO safety filters
                response = model.generate_content(prompt)
                await ctx.send(response.text[:2000])
            
            await log_usage(ctx, "ask", prompt)
        except Exception as e:
            # If an error still happens, print it clearly.
            await ctx.send(f"⚠️ AI Error: {e}")

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

# --- ROBUST IMAGE GENERATION ---
@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    if not await check_channel(ctx): return

    async with ctx.typing():
        try:
            # 1. URL Encode the prompt to handle long text/symbols
            clean_prompt = urllib.parse.quote(prompt)
            # 2. Add a random seed to prevent caching same results
            seed = random.randint(1, 99999)
            # 3. Use a robust model (flux)
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
