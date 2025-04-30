# 1. Base Image: Use an official Python image. Let's use Python 3.11 (a recent, stable version).
#    'slim' variants are smaller and usually sufficient.
FROM python:3.11-slim

# 2. Set Working Directory: Code will be copied and run from here.
WORKDIR /app

# 3. Set Environment Variables
#    - Ensures print statements and logs appear immediately.
ENV PYTHONUNBUFFERED=1
#    - Standard variable for the port Cloud Run expects the app to listen on.
#      Streamlit will be configured to use this via the CMD instruction.
ENV PORT=8080

# 4. Install System Dependencies (OPTIONAL - Uncomment if 'pip install' fails)
#    We are *not* including these initially because psycopg2-binary and modern wheels
#    often don't require them. If the 'pip install' step below fails with compilation
#    errors (mentioning gcc, etc.), uncomment the following lines:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#    build-essential \
#    # Add other specific system libraries if required by any dependency, e.g.:
#    # libpq-dev # <--- Probably NOT needed due to psycopg2-binary
#    # libffi-dev # <--- Sometimes needed by cryptography
#    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 5. Copy Requirements File FIRST
#    This takes advantage of Docker layer caching. If requirements.txt doesn't change,
#    Docker won't re-run the (potentially long) pip install step on subsequent builds
#    unless the base image or this file changes.
COPY requirements.txt ./

# 6. Install Python Dependencies
#    Upgrade pip first. --no-cache-dir makes the final image slightly smaller.
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy Application Code into the container
#    Copies everything from your project's current directory into the container's /app directory.
COPY . .

# 8. Expose the Port (Informational)
#    Lets Docker know which port the application intends to listen on.
#    Cloud Run uses the PORT env variable and internal routing, but this is good practice.
EXPOSE 8080

# 9. Define the Command to Run the Streamlit Application
#    - Uses the $PORT environment variable automatically provided by Cloud Run.
#    - Uses --server.address=0.0.0.0 to listen on all available network interfaces within the container.
#    - Uses --server.headless=true which is essential for running in a server environment.
#    *** IMPORTANT: Replace 'streamlit_app.py' if your main script has a different name! ***
CMD ["streamlit", "run", "streamlit_app.py", "--server.port", "$PORT", "--server.address", "0.0.0.0", "--server.headless=true"]
