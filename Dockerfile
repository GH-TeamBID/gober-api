FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ODBC Driver 18 for SQL Server
RUN apt-get update && apt-get install -y \
    wget \
    supervisor \
    netcat-openbsd \
    procps \
    curl \
    gnupg2 \
    apt-transport-https \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Remove any existing unixodbc packages to avoid conflicts
RUN apt-get update && apt-get remove -y unixodbc unixodbc-dev libodbc2 libodbccr2 libodbcinst2 unixodbc-common \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Add Microsoft repository for ODBC driver - using Debian 12 (bookworm) repo
RUN curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft-archive-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-archive-keyring.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --allow-downgrades --no-install-recommends unixodbc unixodbc-dev msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Create ODBC configuration with exact driver path
RUN DRIVER_PATH=$(ls /opt/microsoft/msodbcsql18/lib64/libmsodbcsql-*.so.1.1 | head -n 1) && \
    echo "[ODBC Driver 18 for SQL Server]" > /etc/odbcinst.ini && \
    echo "Description=Microsoft ODBC Driver 18 for SQL Server" >> /etc/odbcinst.ini && \
    echo "Driver=${DRIVER_PATH}" >> /etc/odbcinst.ini && \
    echo "UsageCount=1" >> /etc/odbcinst.ini && \
    echo "Threading=2" >> /etc/odbcinst.ini && \
    # Verify driver configuration
    cat /etc/odbcinst.ini && \
    odbcinst -q -d -n "ODBC Driver 18 for SQL Server"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
ENV PYTHONPATH=/app

# Create AWS config directory
RUN mkdir -p /root/.aws/

# Create AWS config file
RUN echo "[default]\n\
region = eu-west-3\n\
[profile 715841348065]\n\
region = eu-north-1\n\
[profile NeptuneLoad]\n\
role_arn = arn:aws:iam::715841348065:role/NeptuneLoadFromS3\n\
source_profile = 715841348065\n\
region = eu-north-1" > /root/.aws/config

# Create AWS credentials file
RUN echo "[715841348065]\n\
aws_access_key_id = AKIA2NK3YEHQZUOTJYI4\n\
aws_secret_access_key = 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" > /root/.aws/credentials

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]