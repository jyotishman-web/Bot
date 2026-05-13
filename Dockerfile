# Use the official Playwright image — has ALL browser deps pre-installed
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Chromium is already installed in this base image — no need to run playwright install

# Copy the rest of the code
COPY . .

# Create temp folder for images
RUN mkdir -p temp_images

# Run the bot
CMD ["python", "bot.py"]

# Copy the rest of the code
COPY . .

# Create temp folder for images
RUN mkdir -p temp_images

# Run the bot
CMD ["python", "bot.py"]
