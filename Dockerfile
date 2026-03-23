FROM python:3.14-slim

WORKDIR /app

# System deps for matplotlib font rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p .tmp/infographics .tmp/charts .tmp/search_cache

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "600", "tools.web_app:app"]
