#!/bin/bash

# Azure SQL Database connection settings
export AZURE_SQL_SERVER="your-server.database.windows.net"
export AZURE_SQL_DATABASE="your-database"
export AZURE_SQL_USERNAME="your-username"
export AZURE_SQL_PASSWORD="your-password"

echo "Azure SQL environment variables set."
echo "To use these variables in your current shell, run:"
echo "source setup_azure_env.sh" 