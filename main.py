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
USER_COOLDOWN = 10  # seconds

AI_CHANNEL_ID = None

USER_USAGE = {}
USER_MEMORY = {}
USER_LAST_CALL = {}

# Analytics
TOTAL_REQUESTS = 0
UNIQUE_USERS = set()

MODEL = "llama-3.1-8b-instant"

# ================== DISCORD ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# ================== SMART ANSWER LOGIC ==================
def get_response_style(prompt: str) -> str:
    """
    Decide how long / detailed the answer should be
    """
    text = prompt.lower().strip()
    words = len(text.split())

    if words <= 3:
        return "Reply in one very short sentence or phrase."

    if text.startswith(("what is", "who is", "when", "where", "define")):
        return "Reply in 1–2 short sentences. Be factual."

    if text.startswith(("how", "why", "explain")):
        return "Explain clearly in 4–6 sentences. Stay focused."

    return "Answer clearly and accurately. Avoid unnecessary detail."

# ================== AI CORE ==================
def ask_ai(user_id, prompt, image_url=None):
    global CURRENT_KEY_INDEX, TOTAL_REQUESTS

    now = time.time()

    # ---- Per-user cooldown ----
    last = USER_LAST_CALL.get(user_id, 0)
    if now - last < USER_COOLDOWN:
        return f"⏳ Please wait `{int(USER_COOLDOWN - (now-last))}s` before asking again."

    USER_LAST_CALL[user_id] = now

    # ---- Daily limit ----
    usage = USER_USAGE.setdefault(user_id, {"count": 0, "time": now})
    if now - usage["time"] > 86400:
        USER_USAGE[user_id] = {"count": 0, "time": now}

    if USER_USAGE[user_id]["count"] >= DAILY_LIMIT:
        return "🚫 **Daily AI limit reached (20/day).**"

    USER_USAGE[user_id]["count"] += 1

    # ---- Analytics ----
    TOTAL_REQUESTS += 1
    UNIQUE_USERS.add(user_id)

    # ---- Memory ----
    memory = USER_MEMORY.setdefault(user_id, [])
    memory.append({"role": "user", "content": prompt})
    memory[:] = memory[-MEMORY_SIZE:]

    style_instruction = get_response_style(prompt)

    attempts = 0
    while attempts < len(ALL_KEYS):
        key = ALL_KEYS[CURRENT_KEY_INDEX]
        if now < KEY_COOLDOWNS.get(key, 0):
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(ALL_KEYS)
            attempts += 1
            continue

        try:
            client = Groq(api_key=key)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a precise AI assistant.\n"
                        "Answer exactly what is asked.\n"
                        f"{style_instruction}\n"
                        "Do not add extra information or summaries unless asked."
                    )
                }
            ] + memory

            if image_url:
                img = base64.b64encode(requests.get(image_url).content).decode()
                messages[-1]["content"] = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}
                ]

            res = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=200
            )

            reply = res.choices[0].message.content
            memory.append({"role": "assistant", "content": reply})
            return reply

        except RateLimitError:
            KEY_COOLDOWNS[key] = now + KEY_RETRY_AFTER
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(ALL_KEYS)
            attempts += 1

    return "⏳ AI is busy. Please try again shortly."

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"⚡ Connected as {bot.user}")

# ================== HELP ==================
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🤖 Learn AI – Commands",
        description="Smart AI assistant with precise answers.",
        color=0x00C2FF
    )
    embed.add_field(
        name="🧠 AI",
        value=(
            "`$ask <question>` – Ask anything (supports images)\n"
            "`$translate <text>` – Translate between any languages\n"
            "`$rewrite <text>` – Rewrite professionally\n"
            "`$fixgrammar <text>` – Fix grammar & clarity\n"
            "`$clearcontext` – Clear your AI memory"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Info",
        value="`$usage` – Your daily usage\n`$status` – Bot status\n`$ping` – Latency",
        inline=False
    )

    if ctx.author.guild_permissions.administrator:
        embed.add_field(
            name="🔐 Admin",
            value="`$setaichannel #channel`\n`$analytics`",
            inline=False
        )

    await ctx.send(embed=embed)

# ================== STATUS ==================
@bot.command()
async def status(ctx):
    embed = discord.Embed(title="🟢 Learn AI Status", color=0x2ECC71)
    embed.add_field(name="🧠 Memory", value=f"{MEMORY_SIZE} messages", inline=True)
    embed.add_field(name="📍 AI Channel", value="Not set" if not AI_CHANNEL_ID else f"<#{AI_CHANNEL_ID}>", inline=True)
    embed.add_field(name="⚡ Model", value=MODEL, inline=True)
    embed.add_field(name="🔑 API Keys", value=str(len(ALL_KEYS)), inline=True)
    embed.add_field(name="📊 Daily Limit", value=f"{DAILY_LIMIT}/user", inline=True)
    embed.add_field(name="⏱ Cooldown", value=f"{USER_COOLDOWN}s/user", inline=True)
    await ctx.send(embed=embed)

# ================== USAGE ==================
@bot.command()
async def usage(ctx):
    used = USER_USAGE.get(ctx.author.id, {"count": 0})["count"]
    embed = discord.Embed(
        title="📊 Your AI Usage",
        description=f"You have used **{used}/{DAILY_LIMIT}** requests today.",
        color=0xF1C40F
    )
    await ctx.send(embed=embed)

# ================== CLEAR CONTEXT ==================
@bot.command()
async def clearcontext(ctx):
    USER_MEMORY.pop(ctx.author.id, None)
    await ctx.send("🧹 **Your AI memory has been cleared.**")

# ================== ANALYTICS ==================
@bot.command()
@commands.has_permissions(administrator=True)
async def analytics(ctx):
    embed = discord.Embed(title="📈 AI Analytics", color=0x9B59B6)
    embed.add_field(name="Total Requests", value=str(TOTAL_REQUESTS), inline=True)
    embed.add_field(name="Unique Users", value=str(len(UNIQUE_USERS)), inline=True)
    embed.add_field(name="API Keys", value=str(len(ALL_KEYS)), inline=True)
    await ctx.send(embed=embed)

# ================== ADMIN ==================
@bot.command()
@commands.has_permissions(administrator=True)
async def setaichannel(ctx, channel: discord.TextChannel):
    global AI_CHANNEL_ID
    AI_CHANNEL_ID = channel.id
    await ctx.send(f"✅ **AI locked to {channel.mention}**")

# ================== USER COMMANDS ==================
@bot.command()
async def ask(ctx, *, prompt: str):
    if AI_CHANNEL_ID and ctx.channel.id != AI_CHANNEL_ID:
        return
    img = ctx.message.attachments[0].url if ctx.message.attachments else None
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, prompt, img)
        await ctx.send(reply[:2000])

@bot.command()
async def translate(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Translate this text to the target language mentioned:\n{text}")
        await ctx.send(reply)

@bot.command()
async def rewrite(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Rewrite this professionally:\n{text}")
        await ctx.send(reply)

@bot.command()
async def fixgrammar(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Fix grammar and improve clarity:\n{text}")
        await ctx.send(reply)

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# ================== RUN ==================
keep_alive()
bot.run(DISCORD_TOKEN)
