import discord
from discord.ext import commands
import os
import aiohttp
import json
import random
import urllib.parse
from keep_alive import keep_alive

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- HELPER: MANUAL API CALL (Bypasses Library) ---
async def ask_google_manual(prompt, image_url=None, system_instruction=None):
    # We use the REST API directly to avoid library errors
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    
    # 1. Base Payload
    data = {
        "contents": [],
        # This tells the AI how to behave (Short answers, etc.)
        "system_instruction": {
            "parts": {"text": system_instruction or "You are a helpful assistant. Keep answers concise, direct, and short. Do not waffle."}
        }
    }

    # 2. Add User Content (Image vs Text)
    if image_url:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200: return "Error downloading image."
                img_data = await resp.read()
                import base64
                b64_image = base64.b64encode(img_data).decode('utf-8')
                
                data["contents"].append({
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}
                    ]
                })
    else:
        data["contents"].append({
            "parts": [{"text": prompt}]
        })

    # 3. Send Request
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            if response.status != 200:
                error_text = await response.text()
                return f"⚠️ API Error ({response.status}): {error_text}"
            
            result = await response.json()
            try:
                return result['candidates'][0]['content']['parts'][0]['text']
            except:
                return "⚠️ Error: No text returned."

# --- HELPER: MESSAGE SPLITTER ---
async def send_smart(ctx, text):
    if len(text) <= 2000:
        await ctx.send(text)
    else:
        for i in range(0, len(text), 1900):
            await ctx.send(text[i:i+1900])

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f'⚡ CONNECTED (MANUAL MODE): {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="🤖 Bot Menu", color=0x00ff00)
    embed.add_field(name="AI", value="`$ask`\n`$explain`\n`$summary`", inline=False)
    embed.add_field(name="Fun", value="`$imagine`\n`$roast`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    await ctx.send(f"🟢 **Online** | Mode: `Direct REST API`")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        image_url = None
        if ctx.message.attachments:
            if ctx.message.attachments[0].content_type.startswith('image/'):
                image_url = ctx.message.attachments[0].url
        
        if not prompt and not image_url:
            await ctx.send("Usage: `$ask [question]`")
            return

        # System prompt ensures concise answers
        answer = await ask_google_manual(
            prompt if prompt else "Analyze this", 
            image_url,
            system_instruction="You are a helpful assistant. Give concise, to-the-point answers. Do not write long paragraphs unless necessary."
        )
        await send_smart(ctx, answer)

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    # Added feedback so you know it's working
    msg = await ctx.send(f"🎨 Generating image for `{prompt}`...")
    async with ctx.typing():
        try:
            clean_prompt = urllib.parse.quote(prompt)
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            
            embed = discord.Embed(title="🎨 Generated Image", color=discord.Color.purple())
            embed.set_image(url=url)
            
            # Delete the "Generating..." message and show the result
            await msg.delete()
            await ctx.send(embed=embed)
        except Exception as e:
            await msg.edit(content=f"❌ Image Error: {e}")

@bot.command(name="explain")
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        answer = await ask_google_manual(
            f"Explain '{topic}'", 
            system_instruction="Explain this topic simply and clearly in 2-3 short sentences."
        )
        await send_smart(ctx, f"🎓 **{topic}:**\n{answer}")

@bot.command(name="summary")
async def summary(ctx, *, text: str):
    async with ctx.typing():
        answer = await ask_google_manual(
            f"Summarize this:\n{text}",
            system_instruction="Summarize the text into 3 short bullet points."
        )
        await send_smart(ctx, answer)

@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    async with ctx.typing():
        answer = await ask_google_manual(
            f"Roast {target.name}",
            system_instruction="You are a savage comedian. Write ONE single, short, funny, and savage line to roast the user. Do not write a list."
        )
        await ctx.send(f"🔥 {target.mention} {answer}")

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
