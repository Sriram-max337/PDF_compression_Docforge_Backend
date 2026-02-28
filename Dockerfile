FROM python:3.11-slim

RUN apt-get update && apt-get install -y ghostscript libreoffice-common

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir fastapi uvicorn python-multipart

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]