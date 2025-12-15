import discord
from discord.ext import commands
import os
import random
import urllib.parse
from groq import Groq, RateLimitError
from keep_alive import keep_alive

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# LOAD KEYS: Expects "gsk_1,gsk_2,gsk_3" (Comma separated, no spaces)
keys_string = os.getenv("GROQ_API_KEYS")
if not keys_string:
    print("❌ CRITICAL ERROR: GROQ_API_KEYS is missing in Environment!")
    ALL_KEYS = []
else:
    ALL_KEYS = [k.strip() for k in keys_string.split(',') if k.strip()]

print(f"✅ Loaded {len(ALL_KEYS)} Groq Keys. Cycle Mode Active.")

# GLOBAL INDEX: Remembers which key we are currently using
CURRENT_KEY_INDEX = 0

# --- DISCORD SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

# --- HELPER: ROTATING API CALL ---
def ask_groq_cycle(prompt, system_instruction=None):
    global CURRENT_KEY_INDEX
    
    # We allow the bot to try a full cycle of keys (Length of list)
    # If we have 4 keys, it tries 4 times max before giving up.
    attempts = 0
    max_attempts = len(ALL_KEYS)

    while attempts < max_attempts:
        api_key = ALL_KEYS[CURRENT_KEY_INDEX]
        
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system", 
                        "content": system_instruction or "You are a helpful assistant. Keep answers concise."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stop=None,
                stream=False
            )
            # If successful, we stay on this key (Index doesn't change)
            return completion.choices[0].message.content

        except RateLimitError:
            print(f"⚠️ Key #{CURRENT_KEY_INDEX+1} is out of fuel. Rotating...")
            # Move index to next key (Wraps around: 1->2->3->4->1)
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(ALL_KEYS)
            attempts += 1
            
        except Exception as e:
            print(f"⚠️ Key #{CURRENT_KEY_INDEX+1} Error: {e}. Rotating...")
            # Rotate on other errors too, just in case
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(ALL_KEYS)
            attempts += 1

    return "❌ All API keys are exhausted right now. Please wait a moment."

# --- HELPER: SPLIT MESSAGES ---
async def send_smart(ctx, text):
    if len(text) <= 2000:
        await ctx.send(text)
    else:
        for i in range(0, len(text), 1900):
            await ctx.send(text[i:i+1900])

# --- COMMANDS ---

@bot.event
async def on_ready():
    print(f'⚡ CONNECTED (CYCLE MODE): {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="$help"))

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(title="🤖 Bot Menu (Infinite Cycle)", color=0xf55525)
    embed.add_field(name="AI", value="`$ask`\n`$explain`\n`$summary`", inline=False)
    embed.add_field(name="Fun", value="`$imagine`\n`$roast`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.command(name="status")
async def status(ctx):
    # Shows which key # is currently active
    await ctx.send(f"🟢 **Online** | Active Key: `#{CURRENT_KEY_INDEX + 1}` of `{len(ALL_KEYS)}`")

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        if ctx.message.attachments:
            await ctx.send("❌ Text only for now!")
            return
        if not prompt:
            await ctx.send("Usage: `$ask [question]`")
            return

        answer = ask_groq_cycle(prompt)
        await send_smart(ctx, answer)

@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    msg = await ctx.send(f"🎨 Generating `{prompt}`...")
    async with ctx.typing():
        try:
            clean_prompt = urllib.parse.quote(prompt)
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
            embed = discord.Embed(title="🎨 Generated Image", color=discord.Color.purple())
            embed.set_image(url=url)
            await msg.delete()
            await ctx.send(embed=embed)
        except Exception as e:
            await msg.edit(content=f"❌ Error: {e}")

@bot.command(name="explain")
async def explain(ctx, *, topic: str):
    async with ctx.typing():
        answer = ask_groq_cycle(f"Explain '{topic}'", system_instruction="Explain this simply in 2 sentences.")
        await send_smart(ctx, f"🎓 **{topic}:**\n{answer}")

@bot.command(name="summary")
async def summary(ctx, *, text: str):
    async with ctx.typing():
        answer = ask_groq_cycle(f"Summarize this:\n{text}", system_instruction="Summarize into 3 bullet points.")
        await send_smart(ctx, answer)

@bot.command(name="roast")
async def roast(ctx, member: discord.Member = None):
    target = member if member else ctx.author
    async with ctx.typing():
        answer = ask_groq_cycle(f"Roast {target.name}", system_instruction="You are a savage comedian. Write ONE short, funny roast.")
        await ctx.send(f"🔥 {target.mention} {answer}")

# --- ADMIN ---
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
