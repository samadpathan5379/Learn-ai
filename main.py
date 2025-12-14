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

# --- SMART MODEL SELECTOR (The Fix) ---
# This function asks Google what models are actually available to your key
# and picks the best one automatically.
def get_model():
    try:
        print("🔍 Searching for available models...")
        supported_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                supported_models.append(m.name)
        
        print(f"📋 Google says you can use: {supported_models}")
        
        # Priority list: Try these in order
        preferences = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']
        
        for pref in preferences:
            if pref in supported_models:
                print(f"✅ Auto-selected model: {pref}")
                return genai.GenerativeModel(pref)
        
        # If none match, just grab the first valid one
        if supported_models:
            print(f"⚠️ specific preference not found. Using: {supported_models[0]}")
            return genai.GenerativeModel(supported_models[0])
            
    except Exception as e:
        print(f"⚠️ Auto-detect failed: {e}. Falling back to 'gemini-pro'")
    
    return genai.GenerativeModel('gemini-pro')

model = get_model()

# --- SETUP DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command(name="ask")
async def ask(ctx, *, prompt: str = ""):
    async with ctx.typing():
        try:
            # Check for image
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
                        
                        if len(response.text) > 2000:
                            await ctx.send(response.text[:2000])
                        else:
                            await ctx.send(response.text)
            else:
                # Text only
                if not prompt:
                    await ctx.send("Usage: `!ask [question]`")
                    return
                
                response = model.generate_content(prompt)
                if len(response.text) > 2000:
                    await ctx.send(response.text[:2000])
                else:
                    await ctx.send(response.text)

        except Exception as e:
            # If it fails, print the exact error to Discord so we see it
            await ctx.send(f"❌ Error: {e}")

keep_alive()
bot.run(DISCORD_TOKEN)
