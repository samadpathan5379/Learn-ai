import discord
from discord.ext import commands
import os, time
from groq import Groq, RateLimitError
from keep_alive import keep_alive

# ================= CONFIG =================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
KEYS_STRING = os.getenv("GROQ_API_KEYS")

ALL_KEYS = [k.strip() for k in KEYS_STRING.split(",") if k.strip()]
TOTAL_KEYS = len(ALL_KEYS)

CURRENT_KEY_INDEX = 0
ACTIVE_KEY_NUMBER = 1
KEY_COOLDOWNS = {}
KEY_RETRY_AFTER = 25

DAILY_LIMIT = 20
USER_COOLDOWN = 5
MEMORY_SIZE = 8

AI_CHANNEL_ID = None

USER_USAGE = {}
USER_LAST_CALL = {}
USER_MEMORY = {}

TOTAL_REQUESTS = 0
UNIQUE_USERS = set()

MODEL = "llama-3.1-8b-instant"

# ================= DISCORD =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# ================= SMART RESPONSE =================
def get_response_style(prompt: str):
    p = prompt.lower().strip()
    words = len(p.split())

    if words <= 3:
        return "Reply in one short sentence."
    if p.startswith(("what is", "who is", "define", "when", "where")):
        return "Reply in 1–2 short sentences. Be factual."
    if p.startswith(("how", "why", "explain")):
        return "Explain clearly in 4–6 sentences."
    return "Answer clearly and accurately. Avoid unnecessary detail."

# ================= AI CORE =================
def ask_ai(user_id, prompt):
    global CURRENT_KEY_INDEX, ACTIVE_KEY_NUMBER, TOTAL_REQUESTS

    now = time.time()

    # Cooldown
    last = USER_LAST_CALL.get(user_id, 0)
    if now - last < USER_COOLDOWN:
        return f"⏳ Please wait `{int(USER_COOLDOWN - (now - last))}s`."

    USER_LAST_CALL[user_id] = now

    # Daily limit
    usage = USER_USAGE.setdefault(user_id, {"count": 0, "time": now})
    if now - usage["time"] > 86400:
        USER_USAGE[user_id] = {"count": 0, "time": now}

    if USER_USAGE[user_id]["count"] >= DAILY_LIMIT:
        return "🚫 Daily AI limit reached (20/day)."

    USER_USAGE[user_id]["count"] += 1

    TOTAL_REQUESTS += 1
    UNIQUE_USERS.add(user_id)

    memory = USER_MEMORY.setdefault(user_id, [])
    memory.append({"role": "user", "content": prompt})
    memory[:] = memory[-MEMORY_SIZE:]

    style = get_response_style(prompt)

    attempts = 0
    while attempts < TOTAL_KEYS:
        key = ALL_KEYS[CURRENT_KEY_INDEX]

        if now < KEY_COOLDOWNS.get(key, 0):
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % TOTAL_KEYS
            attempts += 1
            continue

        try:
            ACTIVE_KEY_NUMBER = CURRENT_KEY_INDEX + 1
            client = Groq(api_key=key)

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a precise AI assistant.\n"
                        "Answer exactly what is asked.\n"
                        f"{style}\n"
                        "Do not add extra information unless asked."
                    )
                }
            ] + memory

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
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % TOTAL_KEYS
            attempts += 1

        except Exception as e:
            return f"❌ AI error: {e}"

    return "⏳ AI is busy. Please try again shortly."

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"⚡ Connected as {bot.user}")

# ================= COMMANDS =================
@bot.command()
async def ask(ctx, *, prompt: str):
    if AI_CHANNEL_ID and ctx.channel.id != AI_CHANNEL_ID:
        return
    if ctx.message.attachments:
        await ctx.send("🖼️ Image input is not supported yet.")
        return
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, prompt)
        await ctx.send(reply[:2000])

@bot.command()
async def translate(ctx, *, text: str):
    async with ctx.typing():
        reply = ask_ai(ctx.author.id, f"Translate this text to the target language:\n{text}")
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
async def clearcontext(ctx):
    USER_MEMORY.pop(ctx.author.id, None)
    await ctx.send("🧹 Your AI memory has been cleared.")

@bot.command()
async def usage(ctx):
    used = USER_USAGE.get(ctx.author.id, {"count": 0})["count"]
    await ctx.send(f"📊 You used **{used}/{DAILY_LIMIT}** requests today.")

@bot.command()
async def status(ctx):
    await ctx.send(
        f"🟢 **Learn AI Status**\n"
        f"🧠 Memory: {MEMORY_SIZE} messages\n"
        f"🔑 API Keys: {TOTAL_KEYS}\n"
        f"⚡ Active Key: #{ACTIVE_KEY_NUMBER}\n"
        f"📊 Daily Limit: {DAILY_LIMIT}/user\n"
        f"⏱ Cooldown: {USER_COOLDOWN}s/user"
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def setaichannel(ctx, channel: discord.TextChannel):
    global AI_CHANNEL_ID
    AI_CHANNEL_ID = channel.id
    await ctx.send(f"✅ AI locked to {channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def analytics(ctx):
    await ctx.send(
        f"📈 Analytics\n"
        f"Total Requests: {TOTAL_REQUESTS}\n"
        f"Unique Users: {len(UNIQUE_USERS)}"
    )

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# ================= RUN =================
keep_alive()
bot.run(DISCORD_TOKEN)
