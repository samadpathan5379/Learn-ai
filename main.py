print("🔥 GROQ BOT LOADED")

import discord
from discord.ext import commands
import os
import time
from dotenv import load_dotenv
from groq import Groq
from keep_alive import keep_alive

# ================= LOAD ENV =================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN missing")

if not GROQ_API_KEY:
    raise RuntimeError("❌ GROQ_API_KEY missing")

# ================= GROQ CLIENT =================
client = Groq(api_key=GROQ_API_KEY)

# Preferred models (Groq updates often)
PREFERRED_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "mixtral-8x7b-32768"
]

def get_working_model():
    available = client.models.list().data
    names = [m.id for m in available]

    for model in PREFERRED_MODELS:
        if model in names:
            print(f"✅ Using Groq model: {model}")
            return model

    raise RuntimeError("❌ No supported Groq model found")

MODEL_NAME = get_working_model()

# ================= COOLDOWN =================
LAST_CALL = 0
COOLDOWN = 3  # seconds (Groq is fast, keep low)

def safe_generate(prompt):
    global LAST_CALL

    now = time.time()
    if now - LAST_CALL < COOLDOWN:
        return "⏳ Slow down a bit, try again in a moment."

    try:
        LAST_CALL = now
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Be short, clear, and direct."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content

    except Exception as e:
        if "rate" in str(e).lower():
            return "🚫 Rate limit hit. Try again shortly."
        return f"❌ AI Error: {e}"

# ================= DISCORD BOT =================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"🚀 Logged in as {bot.user}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="$help"
        )
    )

# ================= COMMANDS =================
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🤖 Learn AI (Groq)", color=0x2ecc71)
    embed.add_field(name="AI", value="`$ask <question>`\n`$explain <topic>`", inline=False)
    embed.add_field(name="Fun", value="`$roast @user`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def ask(ctx, *, prompt: str):
    async with ctx.typing():
        reply = safe_generate(prompt)
        await ctx.send(reply[:2000])

@bot.command()
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        reply = safe_generate(f"Explain {topic} in very simple words.")
        await ctx.send(reply[:2000])

@bot.command()
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    reply = safe_generate(f"Roast {target.name} in one short funny line.")
    await ctx.send(f"🔥 {target.mention} {reply}")

# ================= RUN =================
keep_alive()
bot.run(DISCORD_TOKEN)
