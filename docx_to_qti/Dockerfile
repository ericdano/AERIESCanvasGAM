FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files from the current local directory into /app
COPY . .

# Ensure the log file exists so the volume mount doesn't create a directory
RUN touch docx_to_qti.log

EXPOSE 5000

CMD ["python", "app.py"]