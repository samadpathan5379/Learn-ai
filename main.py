import discord
from discord.ext import commands
import google.generativeai as genai
import os
import aiohttp
from keep_alive import keep_alive

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- SETUP GEMINI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

# --- SETUP DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# --- FEATURE 1: CHAT & VISION ---
@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        try:
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                if not attachment.content_type.startswith('image/'):
                    await ctx.send("Please attach a valid image.")
                    return

                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status != 200:
                            await ctx.send("Failed to download image.")
                            return
                        image_data = await resp.read()

                        image_parts = [{"mime_type": attachment.content_type, "data": image_data}]
                        prompt_text = prompt if prompt else "Describe this image."

                        response = model.generate_content([prompt_text, image_parts[0]])
                        text = response.text
                        if len(text) > 2000:
                            await ctx.send(text[:2000])
                            await ctx.send(text[2000:])
                        else:
                            await ctx.send(text)
            else:
                if not prompt:
                    await ctx.send("Usage: `!ask [question]`")
                    return
                response = model.generate_content(prompt)
                await ctx.send(response.text[:2000])

        except Exception as e:
            await ctx.send(f"Error: {e}")

# --- FEATURE 2: IMAGE GENERATION ---
@bot.command(name="imagine")
async def imagine(ctx, *, prompt: str):
    async with ctx.typing():
        try:
            clean_prompt = prompt.replace(" ", "%20")
            image_url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1024&height=1024&nologo=true"
            embed = discord.Embed(title=f"🎨 Generated: {prompt}", color=discord.Color.random())
            embed.set_image(url=image_url)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Error: {e}")

keep_alive()
bot.run(DISCORD_TOKEN)
