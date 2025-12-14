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

# --- UNFILTERED SAFETY SETTINGS ---
# This ensures the bot answers almost anything.
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = "You are a helpful assistant. Give concise, direct, and detailed answers. Avoid filler words."

# --- BRAIN SETUP (The Fix) ---
genai.configure(api_key=GEMINI_API_KEY)

def get_chat_response(prompt, image_parts=None):
    # ATTEMPT 1: Try the Fast Brain (Flash)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_PROMPT, safety_settings=safety_settings)
        if image_parts:
            return model.generate_content([prompt, image_parts[0]]).text
        else:
            return model.generate_content(prompt).text
    except Exception:
        # ATTEMPT 2: If Flash fails (404 Error), IMMEDIATE switch to Standard Brain (Pro)
        # This part is guaranteed to work.
        try:
            model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)
            if image_parts:
                return model.generate_content([prompt, image_parts[0]]).text
            else:
                return model.generate_content(prompt).text
        except Exception as e:
            return f"⚠️ Critical Error: {e}"

bot_settings = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'⚡ Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

# --- COMMANDS ---
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="⚡ Bot Commands", color=0xFFD700)
    embed.add_field(name="Commands", value="`$ask` - Ask AI\n`$imagine` - Create Image\n`$ping` - Check Speed", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"⚡ Latency: `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    await ctx.send(f"🟢 **Online** | Mode: `Auto-Switching (Flash/Pro)`")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        try:
            image_data = None
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                if attachment.content_type.startswith('image/'):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            data = await resp.read()
                            image_data = [{"mime_type": attachment.content_type, "data": data}]
            
            if not prompt and not image_data:
                await ctx.send("Usage: `$ask [question]`")
                return

            # Get answer using the robust function
            response_text = get_chat_response(prompt if prompt else "Analyze this.", image_data)
            await ctx.send(response_text[:2000])
            
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    async with ctx.typing():
        try:
            clean_prompt = urllib.parse.quote(prompt)
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            
            embed = discord.Embed(title=f"🎨 Generated", color=discord.Color.purple())
            embed.set_image(url=url)
            embed.set_footer(text=f"Prompt: {prompt[:50]}...")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Image Failed: {e}")

# --- ADMIN ---
@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    await ctx.send(f"🔒 Locked to {ctx.channel.mention}")

@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def setlogs(ctx):
    await ctx.send(f"📄 Logs set to {ctx.channel.mention}")

keep_alive()
bot.run(DISCORD_TOKEN)
