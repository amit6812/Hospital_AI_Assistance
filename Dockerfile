#FROM python:3.10-slim
FROM public.ecr.aws/docker/library/python:3.10-slim
#WORKDIR /app
WORKDIR ${LAMBDA_TASK_ROOT}
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt
COPY . .

#EXPOSE 8000

CMD ["main.handler"]
#CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
