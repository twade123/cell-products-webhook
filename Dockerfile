FROM python:3.11-slim

WORKDIR /app

COPY requirements-webhook.txt .
RUN pip install -r requirements-webhook.txt

COPY complete_subaccount_creation_standalone.py .

EXPOSE 8080

CMD ["python", "complete_subaccount_creation.py"]
