FROM python:3.11-slim-bookworm

# System dependencies für PJSIP und Audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    swig \
    libasound2-dev \
    libssl-dev \
    libopus-dev \
    libspeex-dev \
    libspeexdsp-dev \
    libportaudio2 \
    portaudio19-dev \
    libsrtp2-dev \
    libsndfile1 \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# PJSIP von Source bauen (für beste Codec-Unterstützung)
WORKDIR /tmp
RUN git clone --depth 1 --branch 2.14.1 https://github.com/pjsip/pjproject.git && \
    cd pjproject && \
    ./configure --enable-shared \
        --with-opus=/usr \
        --with-openssl=/usr \
        CFLAGS="-fPIC -O2" && \
    make dep && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# PJSUA2 Python bindings
RUN cd /tmp/pjproject/pjsip-apps/src/swig/python && \
    make && \
    python setup.py install && \
    rm -rf /tmp/pjproject

# App Verzeichnis
WORKDIR /app

# Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App Code
COPY app/ .

# Katalog-Daten (Multi-Hersteller)
COPY system_katalog/ ./system_katalog/

# SIP Port (UDP + TCP) und API Port
EXPOSE 5060/udp
EXPOSE 5060/tcp
EXPOSE 8080

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "main.py"]
