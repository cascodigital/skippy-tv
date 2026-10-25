FROM python:3.12-slim
RUN pip install --no-cache-dir pillow==11.0.0
WORKDIR /app
COPY app.py ponte.html wallpaper.jpg ./
COPY fonts ./fonts
CMD ["python", "-u", "app.py"]
