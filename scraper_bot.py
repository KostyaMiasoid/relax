import os
import discord
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
import threading
from flask import Flask
import datetime
from zoneinfo import ZoneInfo
import motor.motor_asyncio
import certifi

BOT_TOKEN = os.environ.get("DISCORD_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

TARGET_CHANNEL_ID = 1552023417539133551 

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

if MONGO_URI:
    mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
    db = mongo_client.relax_bot
    ban_collection = db.banned_links
else:
    print("Помилка: Не знайдено MONGO_URI!")
    ban_collection = None

async def get_banned_links():
    if ban_collection is None:
        return set()
    docs = await ban_collection.find({}).to_list(length=None)
    return set(doc["url"] for doc in docs)

async def ban_link(url):
    if ban_collection is not None:
        exists = await ban_collection.find_one({"url": url})
        if not exists:
            await ban_collection.insert_one({"url": url})

class ProfileView(discord.ui.View):
    def __init__(self, profile_url):
        super().__init__(timeout=None)
        self.profile_url = profile_url

    @discord.ui.button(label="Залишити", style=discord.ButtonStyle.green, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Анкету залишено.", ephemeral=True)

    @discord.ui.button(label="В бан", style=discord.ButtonStyle.red, emoji="❌")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ban_link(self.profile_url)
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🚫 Повію додано в бан-лист! Вона більше не з'явиться.", ephemeral=True)

async def scrape_site():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("https://relaxdnepr.com")
        await page.wait_for_load_state("networkidle")
        
        await page.locator("a:has-text('Проверенные')").first.click()
        await page.wait_for_load_state("networkidle")
        
        await page.locator("button[data-target='#services-filter']").click()
        await page.wait_for_timeout(1500)
        
        await page.locator("a:has-text('Работаю с девственниками')").first.click()
        await page.wait_for_load_state("networkidle")

        try:
            search_button = page.locator("form.form-search button[type='submit']")
            if await search_button.is_visible(timeout=2000):
                await search_button.click()
                await page.wait_for_load_state("networkidle")
        except:
            pass
        
        profiles = await page.locator(".item").all()
        for profile in profiles:
            try:
                link_element = profile.locator(".title a")
                profile_link = await link_element.get_attribute("href")
                
                img_element = profile.locator(".visual img").first
                img_path = await img_element.get_attribute("data-src")
                img_url = f"https://relaxdnepr.com{img_path}" if img_path.startswith("/") else img_path
                
                results.append({"url": profile_link, "img": img_url})
            except:
                continue

        await browser.close()
    return results

target_time = datetime.time(hour=12, minute=0, tzinfo=ZoneInfo("Europe/Kyiv"))

@tasks.loop(time=target_time)
async def auto_parse():
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel is None:
        print("Помилка: Не знайдено канал для авто-парсингу")
        return

    print("Запуск пошуку повій о 12:00...")
    banned_links = await get_banned_links()
    profiles = await scrape_site()
    
    sent_count = 0
    for profile in profiles:
        url = profile["url"]
        
        if url in banned_links:
            continue
            
        embed = discord.Embed(title="Нова повія! (Авто-пошук)", url=url, color=discord.Color.green())
        embed.set_image(url=profile["img"])
        
        await channel.send(embed=embed, view=ProfileView(url))
        sent_count += 1
        
    if sent_count > 0:
        await channel.send(f"Знайдено нових повій (автоматично): {sent_count}")
    else:
        print("Авто-парсинг завершено, нових повій немає.")

@bot.command(name="parse")
async def start_parsing(ctx):
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    
    if channel is None:
        await ctx.send("❌ Помилка: Не можу знайти канал! Перевір ID та дозволи бота.")
        return

    await channel.send("Починаю збір повій...")
    
    banned_links = await get_banned_links()
    profiles = await scrape_site()
    
    sent_count = 0
    for profile in profiles:
        url = profile["url"]
        
        if url in banned_links:
            continue
            
        embed = discord.Embed(title="Нова повія!", url=url, color=discord.Color.blue())
        embed.set_image(url=profile["img"])
        
        await channel.send(embed=embed, view=ProfileView(url))
        sent_count += 1
        
    await channel.send(f"Знайдено нових повій: {sent_count}")

@bot.event
async def on_ready():
    print(f'Бот {bot.user} успішно запущений!')
    print('Напиши в Discord команду !parse щоб запустити парсер.')
    
    if not auto_parse.is_running():
        auto_parse.start()

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("Помилка: Не знайдено токен бота!")
