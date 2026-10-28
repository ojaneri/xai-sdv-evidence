# Tier 1 and tier 2 environment (CPU only).
#   docker build -t xai-sdv-evidence .
#   docker run --rm xai-sdv-evidence                       # tier 1
#   docker run --rm -v /path/to/data:/data -e XAI_SDV_DATA=/data \
#       xai-sdv-evidence make tier2-can                    # tier 2, CAN part
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends make gcc libc6-dev libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /repro
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.12.0 torchvision==0.27.0 \
        --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["make", "tier1"]
