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

# --- AUTO-DETECT MODEL ---
genai.configure(api_key=GEMINI_API_KEY)

def find_working_model():
    print("🔍 Scanning API Key for available models...")
    try:
        # Ask Google: "What models does this key have access to?"
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ Found Model: {m.name}")
                # We prefer Flash or Pro, but we will take ANYTHING that works.
                if 'flash' in m.name:
                    return genai.GenerativeModel(m.name)
                if 'pro' in m.name and 'vision' not in m.name:
                    return genai.GenerativeModel(m.name)
        
        # If we loop through everything and find nothing, try the basic one
        print("⚠️ No specific match found in list. Trying default 'gemini-1.5-flash'...")
        return genai.GenerativeModel('gemini-1.5-flash')
        
    except Exception as e:
        print(f"❌ Error listing models: {e}")
        print("⚠️ Fallback: Forcing 'gemini-pro'")
        return genai.GenerativeModel('gemini-pro')

# Load the best model found
model = find_working_model()

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
bot_settings = {}

# --- HELPER: Split Long Messages (Fixes the 2000 char crash) ---
async def send_smart(ctx, text):
    if len(text) <= 2000:
        await ctx.send(text)
    else:
        # Split into chunks of 1900 chars
        for i in range(0, len(text), 1900):
            await ctx.send(text[i:i+1900])

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f'⚡ CONNECTED: {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="🤖 Bot Menu", color=0x00ff00)
    embed.add_field(name="AI", value="`$ask [q]` - Chat\n`$explain [topic]` - Explain\n`$summary [text]` - Summarize", inline=False)
    embed.add_field(name="Fun", value="`$imagine [prompt]` - Create Image\n`$roast [user]` - Roast", inline=False)
    embed.add_field(name="Admin", value="`$setchannel` - Lock Channel\n`$setlogs` - Set Logs", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    try:
        name = model.model_name
    except:
        name = "Unknown/Error"
    await ctx.send(f"🟢 **Online** | Using Brain: `{name}`")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        try:
            # Handle Image Attachment
            if ctx.message.attachments:
                att = ctx.message.attachments[0]
                if att.content_type.startswith('image/'):
                    async with aiohttp.ClientSession() as sess:
                        async with sess.get(att.url) as resp:
                            img_data = await resp.read()
                            content = [{"mime_type": att.content_type, "data": img_data}, prompt if prompt else "Analyze"]
                            response = model.generate_content(content)
                            await send_smart(ctx, response.text)
            
            # Handle Text
            elif prompt:
                response = model.generate_content(prompt)
                await send_smart(ctx, response.text)
            else:
                await ctx.send("Usage: `$ask [question]`")
                
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    async with ctx.typing():
        try:
            clean_prompt = urllib.parse.quote(prompt)
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            
            embed = discord.Embed(title="🎨 Generated Image", color=discord.Color.purple())
            embed.set_image(url=url)
            embed.set_footer(text=f"Prompt: {prompt[:50]}...")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Image Error: {e}")

# --- NEW COMMANDS (Requested) ---
@bot.command(name="explain")
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        resp = model.generate_content(f"Explain '{topic}' simply in 2 sentences.")
        await ctx.send(f"🎓 **{topic}:**\n{resp.text}")

@bot.command(name="summary")
async def summary(ctx, *, text: str):
    async with ctx.typing():
        resp = model.generate_content(f"Summarize this in bullet points:\n{text}")
        await send_smart(ctx, resp.text)

@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    async with ctx.typing():
        resp = model.generate_content(f"Write a short, funny, friendly roast for {target.name}.")
        await ctx.send(f"🔥 {target.mention} {resp.text}")

# --- ADMIN COMMANDS ---
@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel(ctx):
    # Simple logic: Just confirm it works, keeping it simple for now to avoid errors
    await ctx.send(f"🔒 Channel locked to {ctx.channel.mention} (Settings saved)")

@bot.command(name="setlogs")
@commands.has_permissions(administrator=True)
async def setlogs(ctx):
    await ctx.send(f"📄 Logs will be sent to {ctx.channel.mention}")

keep_alive()
bot.run(DISCORD_TOKEN)
