FROM python:3.10-slim
# FROM public.ecr.aws/docker/library/python:3.10-slim
WORKDIR /app
# WORKDIR ${LAMBDA_TASK_ROOT}
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt
COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]


#------------------------------------------------------------ For lambda
# FROM public.ecr.aws/lambda/python:3.10
# WORKDIR ${LAMBDA_TASK_ROOT}
# COPY requirement.txt .
# RUN pip install -r requirement.txt
# COPY . .
# CMD [ "main.handler" ]
