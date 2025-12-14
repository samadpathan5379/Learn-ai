import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import google.generativeai as genai
from keep_alive import keep_alive

# LOAD ENV
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# CONFIG GEMINI
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    system_instruction="You are a helpful assistant. Keep answers short, clear, and direct."
)

# DISCORD SETUP
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)

# READY
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="$help"
        )
    )

# HELP
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="🤖 Commands", color=0x2ecc71)
    embed.add_field(name="AI", value="`$ask <question>`\n`$explain <topic>`", inline=False)
    embed.add_field(name="Fun", value="`$roast @user`", inline=False)
    await ctx.send(embed=embed)

# ASK AI
@bot.command()
async def ask(ctx, *, prompt: str):
    async with ctx.typing():
        try:
            response = model.generate_content(prompt)
            await ctx.send(response.text[:2000])
        except Exception as e:
            await ctx.send(f"❌ Error: {e}")

# EXPLAIN
@bot.command()
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        response = model.generate_content(f"Explain {topic} in simple words.")
        await ctx.send(response.text[:2000])

# ROAST
@bot.command()
async def roast(ctx, member: discord.Member = None):
    target = member or ctx.author
    prompt = f"Roast {target.name} in one short funny line."
    async with ctx.typing():
        response = model.generate_content(prompt)
        await ctx.send(f"🔥 {target.mention} {response.text}")

# KEEP ALIVE
keep_alive()
bot.run(DISCORD_TOKEN)
