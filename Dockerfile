FROM python:3.9-slim

WORKDIR /app

# Install SSL certificates and dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc python3-dev libpq-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install -r requirements.txt

# Copy RDS SSL certificate
COPY global-bundle.pem /etc/ssl/certs/

EXPOSE 8080

CMD ["streamlit", "run", "streamlit_app.py"]
