import os
import discord
from discord.ext import commands
from playwright.async_api import async_playwright
import threading
from flask import Flask

# Беремо токен зі змінних оточення (безпечний підхід)
BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# Налаштування бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

BAN_FILE = "ban_list.txt"

# Функція для завантаження бан-листа з файлу
def get_banned_links():
    if not os.path.exists(BAN_FILE):
        return set()
    with open(BAN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

# Функція для додавання в бан-лист
def ban_link(url):
    with open(BAN_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")

# Клас, який створює кнопки під повідомленням
class ProfileView(discord.ui.View):
    def __init__(self, profile_url):
        super().__init__(timeout=None)
        self.profile_url = profile_url

    # Кнопка "Галочка" (Бездіяльність/Залишити)
    @discord.ui.button(label="Залишити", style=discord.ButtonStyle.green, emoji="✅")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Відключаємо кнопки після натискання
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("Анкету залишено.", ephemeral=True)

    # Кнопка "Хрестик" (Додати в бан-лист)
    @discord.ui.button(label="В бан", style=discord.ButtonStyle.red, emoji="❌")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ban_link(self.profile_url)
        # Відключаємо кнопки
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🚫 Анкету додано в бан-лист! Вона більше не з'явиться.", ephemeral=True)


# Основна функція парсингу (тепер асинхронна)
async def scrape_site():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto("https://relaxdnepr.com")
        await page.wait_for_load_state("networkidle")
        
        # 1. Фільтр "Проверенные"
        await page.locator("a:has-text('Проверенные')").first.click()
        await page.wait_for_load_state("networkidle")
        
        # 2. Відкриваємо "Услуги"
        await page.locator("button[data-target='#services-filter']").click()
        await page.wait_for_timeout(1500)
        
        # 3. Фільтр "Работаю с девственниками"
        await page.locator("a:has-text('Работаю с девственниками')").first.click()
        await page.wait_for_load_state("networkidle")

        # 4. Натискаємо кнопку пошуку (якщо є)
        try:
            search_button = page.locator("form.form-search button[type='submit']")
            if await search_button.is_visible(timeout=2000):
                await search_button.click()
                await page.wait_for_load_state("networkidle")
        except:
            pass
        
        # Збираємо всі анкети
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


# Команда в Discord, яка запускає парсер
@bot.command(name="parse")
async def start_parsing(ctx):
    await ctx.send("⏳ Починаю збір анкет...")
    
    banned_links = get_banned_links()
    profiles = await scrape_site()
    
    sent_count = 0
    for profile in profiles:
        url = profile["url"]
        
        # Якщо анкета вже є в txt файлі - пропускаємо її
        if url in banned_links:
            continue
            
        embed = discord.Embed(title="Нова анкета знайдена!", url=url, color=discord.Color.blue())
        embed.set_image(url=profile["img"])
        
        # Відправляємо повідомлення з кнопками
        await ctx.send(embed=embed, view=ProfileView(url))
        sent_count += 1
        
    await ctx.send(f"✅ Готово! Знайдено нових анкет: {sent_count}")

@bot.event
async def on_ready():
    print(f'Бот {bot.user} успішно запущений!')
    print('Напиши в Discord команду !parse щоб запустити парсер.')

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    # Render автоматично видає порт через змінну середовища PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Запускаємо веб-сервер у фоновому потоці
    threading.Thread(target=run_web, daemon=True).start()
    
    # Запускаємо самого бота
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("Помилка: Не знайдено токен бота!")