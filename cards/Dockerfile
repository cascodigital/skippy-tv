FROM python:3.12-slim
RUN pip install --no-cache-dir pillow==11.0.0 tzdata==2025.2
WORKDIR /app
COPY app.py quips.py plexw.py ponte.html wallpaper.jpg house.json ./
COPY fonts ./fonts
CMD ["python", "-u", "app.py"]
