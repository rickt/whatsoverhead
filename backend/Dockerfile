#
# Dockerfile for whatsoverhead
#

# use slim python image
FROM python:3.9-slim

# env
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# set work dir
WORKDIR /app

# install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# install python deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --root-user-action -r requirements.txt 

# env & app code
COPY .env .
COPY plane_api.py .

# port
EXPOSE 8000

# lets gooo
CMD ["uvicorn", "plane_api:app", "--host", "0.0.0.0", "--port", "8080"]

# EOF

