# Змінюємо образ на Debian 12 (Bookworm), де немає проблем із шрифтами
FROM python:3.10-bookworm

# Встановлюємо робочу директорію всередині контейнера
WORKDIR /app

# Копіюємо файл із залежностями
COPY requirements.txt .

# Встановлюємо Python-залежності
RUN pip install --no-cache-dir -r requirements.txt

# Встановлюємо Chromium та всі необхідні системні бібліотеки для Playwright
RUN playwright install --with-deps chromium

# Копіюємо весь інший код у контейнер
COPY . .

# Вказуємо порт для Flask
ENV PORT=10000
EXPOSE $PORT

# Команда для запуску вашого бота (увага: -u потрібен для логів на Render)
CMD ["python", "-u", "scraper_bot.py"]
