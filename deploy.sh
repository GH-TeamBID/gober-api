#!/bin/bash
set -e

echo "================================"
echo "Deploying to Azure SQL Database"
echo "================================"

# Ensure all dependencies are installed
echo "Installing dependencies..."
pip install -r requirements.txt

# Run migrations using Alembic
echo "Running database migrations..."
alembic upgrade head

# Create admin user using environment variables or defaults
echo "Creating admin user..."
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    python -m app.core.init_db --email "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" --admin-only
else
    python -m app.core.init_db --admin-only
fi

# Initialize other database components
echo "Initializing other database components..."
python -m app.core.init_db --skip-migrations

echo "Deployment completed successfully!" 