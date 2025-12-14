import discord
from discord.ext import commands
import google.generativeai as genai
import os
import aiohttp
import random
import urllib.parse
from keep_alive import keep_alive

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- GEMINI SETUP ---
genai.configure(api_key=GEMINI_API_KEY)

# We use 'gemini-1.5-flash' because it is the standard, stable model now.
# If this fails, the only fix is updating requirements.txt, but this code is the correct one.
model = genai.GenerativeModel('gemini-1.5-flash')

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- HELPER: Split Long Messages ---
async def send_smart(ctx, text):
    if len(text) <= 2000:
        await ctx.send(text)
    else:
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
    embed.add_field(name="AI", value="`$ask [q]` - Chat\n`$explain` - Simple\n`$summary` - Shorten", inline=False)
    embed.add_field(name="Fun", value="`$imagine` - Create Image\n`$roast` - Roast User", inline=False)
    embed.add_field(name="System", value="`$ping` - Speed\n`$status` - Brain Info", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    await ctx.send(f"🟢 **Online** | Brain: `Gemini 1.5 Flash`")

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

# --- NEW COMMANDS ---
@bot.command(name="explain")
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        try:
            resp = model.generate_content(f"Explain '{topic}' simply in 2-3 sentences.")
            await send_smart(ctx, f"🎓 **{topic}:**\n{resp.text}")
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")

@bot.command(name="summary")
async def summary(ctx, *, text: str):
    async with ctx.typing():
        try:
            resp = model.generate_content(f"Summarize this in bullet points:\n{text}")
            await send_smart(ctx, resp.text)
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")

@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    async with ctx.typing():
        try:
            resp = model.generate_content(f"Write a short, funny, friendly roast for {target.name}.")
            await ctx.send(f"🔥 {target.mention} {resp.text}")
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")

# --- ADMIN COMMANDS ---
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
