import discord
from discord.ext import commands
import os, time, base64, requests
from groq import Groq, RateLimitError
from keep_alive import keep_alive

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
KEYS_STRING = os.getenv("GROQ_API_KEYS")

ALL_KEYS = [k.strip() for k in KEYS_STRING.split(",") if k.strip()]
CURRENT_KEY_INDEX = 0
KEY_COOLDOWNS = {}
KEY_RETRY_AFTER = 25

DAILY_LIMIT = 20
MEMORY_SIZE = 8

AI_CHANNEL_ID = None
USER_USAGE = {}
USER_MEMORY = {}
USER_MODEL = {}

MODEL_FAST = "llama-3.1-8b-instant"
MODEL_SMART = "llama3-70b-8192"

# ================== DISCORD ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# ================== AI CORE ==================
def ask_ai(user_id, prompt, image_url=None):
    global CURRENT_KEY_INDEX
    now = time.time()

    if USER_USAGE.get(user_id, {"count":0,"time":now})["count"] >= DAILY_LIMIT:
        return "🚫 Daily AI limit reached (20/day)."

    USER_USAGE.setdefault(user_id, {"count":0,"time":now})
    if now - USER_USAGE[user_id]["time"] > 86400:
        USER_USAGE[user_id] = {"count":0,"time":now}

    USER_USAGE[user_id]["count"] += 1

    memory = USER_MEMORY.setdefault(user_id, [])
    memory.append({"role":"user","content":prompt})
    memory[:] = memory[-MEMORY_SIZE:]

    model = USER_MODEL.get(user_id, MODEL_FAST)

    attempts = 0
    while attempts < len(ALL_KEYS):
        key = ALL_KEYS[CURRENT_KEY_INDEX]
        if now < KEY_COOLDOWNS.get(key,0):
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX+1)%len(ALL_KEYS)
            attempts+=1
            continue
        try:
            client = Groq(api_key=key)
            messages = [{"role":"system","content":"Be concise, clear, helpful."}] + memory
            if image_url:
                img = base64.b64encode(requests.get(image_url).content).decode()
                messages[-1]["content"] = [
                    {"type":"text","text":prompt},
                    {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img}"}}
                ]
            res = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=300
            )
            reply = res.choices[0].message.content
            memory.append({"role":"assistant","content":reply})
            return reply
        except RateLimitError:
            KEY_COOLDOWNS[key]=now+KEY_RETRY_AFTER
            CURRENT_KEY_INDEX=(CURRENT_KEY_INDEX+1)%len(ALL_KEYS)
            attempts+=1
    return "⏳ AI busy. Try again shortly."

# ================== CHECK CHANNEL ==================
async def channel_check(ctx):
    if AI_CHANNEL_ID and ctx.channel.id != AI_CHANNEL_ID:
        return False
    return True

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"⚡ Connected as {bot.user}")

# ================== HELP ==================
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🤖 Learn AI Commands", color=0x00ffcc)
    embed.add_field(name="AI", value="`$ask`\n`$translate`\n`$rewrite`\n`$fixgrammar`\n`$model`\n`$usage`", inline=False)
    if ctx.author.guild_permissions.administrator:
        embed.add_field(name="Admin", value="`$setaichannel`", inline=False)
    await ctx.send(embed=embed)

# ================== STATUS ==================
@bot.command()
async def status(ctx):
    await ctx.send(
        f"🟢 Online\n"
        f"🧠 Memory: {MEMORY_SIZE}\n"
        f"📍 AI Channel: {'Not set' if not AI_CHANNEL_ID else f'<#{AI_CHANNEL_ID}>'}\n"
        f"⚡ Models: fast/smart\n"
        f"🔑 Keys: {len(ALL_KEYS)}\n"
        f"📊 Daily limit: {DAILY_LIMIT}"
    )

# ================== ADMIN ==================
@bot.command()
@commands.has_permissions(administrator=True)
async def setaichannel(ctx, channel: discord.TextChannel):
    global AI_CHANNEL_ID
    AI_CHANNEL_ID = channel.id
    await ctx.send(f"✅ AI locked to {channel.mention}")

# ================== USER ==================
@bot.command()
async def usage(ctx):
    used = USER_USAGE.get(ctx.author.id,{"count":0})["count"]
    await ctx.send(f"📊 You used `{used}/{DAILY_LIMIT}` AI requests today.")

@bot.command()
async def model(ctx, mode: str):
    if mode not in ["fast","smart"]:
        await ctx.send("Use `fast` or `smart`")
        return
    USER_MODEL[ctx.author.id] = MODEL_FAST if mode=="fast" else MODEL_SMART
    await ctx.send(f"⚡ Model set to `{mode}`")

@bot.command()
async def ask(ctx, *, prompt: str):
    if not await channel_check(ctx):
        return
    img = ctx.message.attachments[0].url if ctx.message.attachments else None
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, prompt, img)
        await ctx.send(reply[:2000])

@bot.command()
async def translate(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Translate this to simple Hindi: {text}")
        await ctx.send(reply)

@bot.command()
async def rewrite(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Rewrite this professionally: {text}")
        await ctx.send(reply)

@bot.command()
async def fixgrammar(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Fix grammar and improve clarity: {text}")
        await ctx.send(reply)

# ================== RUN ==================
keep_alive()
bot.run(DISCORD_TOKEN)
