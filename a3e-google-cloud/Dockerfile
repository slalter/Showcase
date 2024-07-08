# Use an official Python runtime as a base image
FROM python:3.11-bookworm

# Set the working directory in the container
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    # Pipenv for managing dependencies
    && pip install pipenv


COPY . /app

RUN PIP_NO_BINARY=psycopg2 pipenv install --deploy


# Set environment variables
ENV FLASK_APP=app.py
# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run the app. Use pipenv to run the app inside the virtualenv
CMD ["pipenv", "run", "python", "app.py"]
#CMD ["sleep","infinity"]