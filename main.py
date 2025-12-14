print("🔥 NEW AUTO-MODEL BOT LOADED")

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import google.generativeai as genai
from keep_alive import keep_alive

# ================= LOAD ENV =================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not DISCORD_TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN not set")

if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY not set")

# ================= GEMINI CONFIG =================
genai.configure(api_key=GEMINI_API_KEY)

def get_working_model():
    """
    Automatically find a Gemini model that supports generateContent
    """
    models = genai.list_models()

    for m in models:
        if "generateContent" in m.supported_generation_methods:
            print(f"✅ Using Gemini model: {m.name}")
            return genai.GenerativeModel(
                model_name=m.name,
                system_instruction="You are a helpful assistant. Be short, clear, and direct."
            )

    raise RuntimeError("❌ No Gemini model supports generateContent")

model = get_working_model()

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
    embed = discord.Embed(title="🤖 Learn AI Bot", color=0x2ecc71)
    embed.add_field(name="AI", value="`$ask <question>`\n`$explain <topic>`", inline=False)
    embed.add_field(name="Fun", value="`$roast @user`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)}ms")

@bot.command()
async def ask(ctx, *, prompt: str):
    async with ctx.typing():
        try:
            response = model.generate_content(prompt)
            await ctx.send(response.text[:2000])
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

@bot.command()
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        response = model.generate_content(
            f"Explain {topic} in very simple words."
        )
        await ctx.send(response.text[:2000])

@bot.command()
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    prompt = f"Roast {target.name} in one short funny line."
    async with ctx.typing():
        response = model.generate_content(prompt)
        await ctx.send(f"🔥 {target.mention} {response.text}")

# ================= RUN =================
keep_alive()
bot.run(DISCORD_TOKEN)
