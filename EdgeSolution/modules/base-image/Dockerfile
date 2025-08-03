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

# Install common Python packages
RUN pip install --no-cache-dir \
    azure-iot-device==2.12.0 \
    openai==1.12.0 \
    openai-whisper==20231117 \
    numpy==1.24.3 \
    python-dotenv==1.0.0

# Pre-download Whisper model
RUN python -c "import whisper; whisper.load_model('base')"

# Add to audio group
RUN usermod -a -G audio root