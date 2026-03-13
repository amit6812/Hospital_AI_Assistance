FROM python:3.10-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt
COPY . .
EXPOSE 8080

ENV PORT=8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]