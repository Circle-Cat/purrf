#!/usr/bin/env bash
set -e

CONTAINER_NAME="my-postgres"
IMAGE="postgres:16"

# Stop & remove existing container if exists
if [ $(docker ps -aq -f name=$CONTAINER_NAME) ]; then
    echo "Removing old container..."
    docker rm -f $CONTAINER_NAME > /dev/null
fi

echo "Starting PostgreSQL container..."
docker run -d \
  --name $CONTAINER_NAME \
  -p 5432:5432 \
  -e POSTGRES_USER=myuser \
  -e POSTGRES_PASSWORD=mypassword \
  -e POSTGRES_DB=mydb \
  $IMAGE

echo "PostgreSQL is running on localhost:5432"
