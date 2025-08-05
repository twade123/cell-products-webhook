FROM python:3.11-slim

WORKDIR /app

COPY requirements-webhook.txt .
RUN pip install -r requirements-webhook.txt

COPY complete_subaccount_creation.py .
COPY Core/config.py ./Core/config.py

# Create Core directory structure
RUN mkdir -p Core

EXPOSE 8080

CMD ["python", "complete_subaccount_creation.py"]
