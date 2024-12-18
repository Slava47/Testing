# Используем официальный образ Python
FROM python:3.9

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем все файлы проекта в контейнер
COPY . .

# Устанавливаем необходимые зависимости
RUN pip install --no-cache-dir \
    pyTelegramBotAPI==4.3.1 \
    Pillow==9.0.0 \
    SQLAlchemy==1.4.27

# Открываем порт, если необходимо (например, для веб-сервиса)
EXPOSE 5000

# Запускаем бота
CMD ["python", "pipi30.py"]
