import discord
from discord.ext import commands
import os
import time
from groq import Groq, RateLimitError
from keep_alive import keep_alive

# ================== CONFIG ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
KEYS_STRING = os.getenv("GROQ_API_KEYS")

if not DISCORD_TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN not set")

if not KEYS_STRING:
    raise RuntimeError("❌ GROQ_API_KEYS not set")

ALL_KEYS = [k.strip() for k in KEYS_STRING.split(",") if k.strip()]
if not ALL_KEYS:
    raise RuntimeError("❌ No valid Groq API keys found")

print(f"✅ Loaded {len(ALL_KEYS)} Groq API keys")

# ================== KEY STATE ==================
CURRENT_KEY_INDEX = 0
KEY_COOLDOWNS = {}          # api_key -> retry timestamp
KEY_RETRY_AFTER = 25        # seconds

# ================== STATUS LOCK ==================
LAST_STATUS_CALL = {}
STATUS_COOLDOWN = 3  # seconds

# ================== DISCORD SETUP ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)

# ================== GROQ ROTATION LOGIC ==================
def ask_groq(prompt, system_instruction=None):
    global CURRENT_KEY_INDEX
    now = time.time()

    # Check if any key is available
    available_keys = [
        k for k in ALL_KEYS
        if now >= KEY_COOLDOWNS.get(k, 0)
    ]

    if not available_keys:
        wait_time = int(min(KEY_COOLDOWNS.values()) - now)
        return f"⏳ AI is cooling down. Try again in {max(wait_time, 1)}s."

    attempts = 0
    max_attempts = len(ALL_KEYS)

    while attempts < max_attempts:
        api_key = ALL_KEYS[CURRENT_KEY_INDEX]

        if now < KEY_COOLDOWNS.get(api_key, 0):
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(ALL_KEYS)
            attempts += 1
            continue

        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": system_instruction or
                        "You are a Discord bot. Reply briefly and clearly. Max 3 sentences."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            return completion.choices[0].message.content

        except RateLimitError:
            KEY_COOLDOWNS[api_key] = now + KEY_RETRY_AFTER

        except Exception as e:
            print(f"⚠️ Key error: {e}")
            KEY_COOLDOWNS[api_key] = now + KEY_RETRY_AFTER

        CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(ALL_KEYS)
        attempts += 1

    return "⏳ AI is busy. Please try again shortly."

# ================== UTILS ==================
async def send_smart(ctx, text):
    if len(text) <= 2000:
        await ctx.send(text)
    else:
        for i in range(0, len(text), 1900):
            await ctx.send(text[i:i+1900])

# ================== EVENTS ==================
@bot.event
async def on_ready():
    print(f"⚡ CONNECTED: {bot.user}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="$help"
        )
    )

# ================== COMMANDS ==================
@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="🤖 Learn AI", color=0xf55525)
    embed.add_field(
        name="AI",
        value="`$ask <question>`\n`$explain <topic>`\n`$summary <text>`",
        inline=False
    )
    embed.add_field(name="Fun", value="`$roast @user`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    uid = ctx.author.id
    now = time.time()

    if now - LAST_STATUS_CALL.get(uid, 0) < STATUS_COOLDOWN:
        return

    LAST_STATUS_CALL[uid] = now
    await ctx.send(
        f"🟢 **Online** | Active Key: `#{CURRENT_KEY_INDEX + 1}` of `{len(ALL_KEYS)}`"
    )

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    if not prompt:
        await ctx.send("Usage: `$ask <question>`")
        return
    async with ctx.typing():
        answer = ask_groq(prompt)
        await send_smart(ctx, answer)

@bot.command(name="explain")
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        answer = ask_groq(
            f"Explain {topic}",
            system_instruction="Explain simply in 2 sentences."
        )
        await send_smart(ctx, f"🎓 **{topic}:**\n{answer}")

@bot.command(name="summary")
async def summary(ctx, *, text: str):
    async with ctx.typing():
        answer = ask_groq(
            f"Summarize:\n{text}",
            system_instruction="Summarize into 3 short bullet points."
        )
        await send_smart(ctx, answer)

@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    async with ctx.typing():
        answer = ask_groq(
            f"Roast {target.name}",
            system_instruction="One short, funny roast."
        )
        await ctx.send(f"🔥 {target.mention} {answer}")

# ================== RUN ==================
keep_alive()
bot.run(DISCORD_TOKEN)
