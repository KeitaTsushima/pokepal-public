FROM arm64v8/python:3.9-slim

# Install system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    alsa-utils \
    ffmpeg \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Azure Infrastructure + Core AI packages
RUN pip install --no-cache-dir \
    azure-iot-device==2.14.0 \
    azure-identity>=1.17.0 \
    azure-keyvault-secrets==4.7.0 \
    openai>=1.35.0 \
    numpy==1.24.3 \
    python-dotenv==1.0.0

# Add to audio group
RUN usermod -a -G audio root