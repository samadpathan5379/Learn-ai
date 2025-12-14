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

# --- SAFETY: UNFILTERED ---
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = "You are a helpful assistant. Give concise, direct answers."

genai.configure(api_key=GEMINI_API_KEY)

# --- SMART MODEL LOADER ---
def get_chat_model():
    # We will prioritize 'gemini-1.5-flash' but fall back to 'gemini-pro' safely
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_PROMPT, safety_settings=safety_settings)
        return model
    except:
        return genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)

bot_settings = {}
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- HELPER: SPLIT LONG MESSAGES ---
async def send_split_message(ctx, text):
    if len(text) <= 2000:
        await ctx.send(text)
    else:
        # Split text into chunks of 1900 characters to be safe
        chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
        for chunk in chunks:
            await ctx.send(chunk)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'⚡ NEW BOT INSTANCE LOGGED IN: {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

# --- COMMANDS ---
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="⚡ Bot Commands", color=0xFFD700)
    embed.add_field(name="Commands", value="`$ask` - Ask AI\n`$imagine` - Create Image\n`$ping` - Check Speed", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    # This helps identify if you have the old bot running
    await ctx.send(f"⚡ Pong! (New Bot ID: {random.randint(100, 999)})")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        try:
            model = get_chat_model()
            response_text = ""

            # Image Handling
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                if attachment.content_type.startswith('image/'):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            data = await resp.read()
                            image_parts = [{"mime_type": attachment.content_type, "data": data}]
                            response = model.generate_content([prompt if prompt else "Analyze this", image_parts[0]])
                            response_text = response.text
            
            # Text Only Handling
            elif prompt:
                response = model.generate_content(prompt)
                response_text = response.text
            else:
                await ctx.send("Usage: `$ask [question]`")
                return

            # SEND RESULT (using the splitter to fix Error 400)
            await send_split_message(ctx, response_text)
            
        except Exception as e:
            # If Flash fails, force a retry with Pro (Manual Fallback)
            try:
                fallback_model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)
                response = fallback_model.generate_content(prompt)
                await send_split_message(ctx, response.text)
            except Exception as e2:
                await ctx.send(f"⚠️ Error: {e2}")

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
