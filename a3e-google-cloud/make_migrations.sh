#!/bin/bash

# Wait for the database container to be ready
echo "Waiting for the database container to be ready..."
docker compose up -d db
# Wait for the PostgreSQL database to be ready
until docker compose exec db psql -U user -d mydatabase -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "starting alembic container..."
docker compose up -d alembic --build

# Create Alembic migration files
echo "Creating Alembic migration files..."
sudo docker compose exec alembic pipenv run alembic revision --autogenerate -m "automigrate"
sleep 1

echo "Migration files created."

docker compose down