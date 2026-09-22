# Використовуємо легкий образ Python
FROM python:3.10-slim

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

# Вказуємо порт для Flask (Render зазвичай використовує 10000)
ENV PORT=10000
EXPOSE $PORT

# Команда для запуску вашого бота (замініть main.py на назву вашого файлу)
CMD ["python", "main.py"]