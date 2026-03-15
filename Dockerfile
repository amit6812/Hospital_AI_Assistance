FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE

EXPOSE 8080

CMD ["gunicorn","-k","uvicorn.workers.UvicornWorker","-b","0.0.0.0:8080","main:app"]