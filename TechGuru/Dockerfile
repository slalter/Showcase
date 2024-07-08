# Use an official Python runtime as a base image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    python3-dev \
    # Pipenv for managing dependencies
    && pip install pipenv


#copy over the pipfile and piplock
COPY Pipfile Pipfile.lock /app/

RUN PIP_NO_BINARY=psycopg2 pipenv install --deploy

COPY . /app

# Set environment variables
ENV FLASK_APP=app.python
EXPOSE 5000

# Run the app. Use pipenv to run the app inside the virtualenv
CMD ["pipenv", "run", "python", "app.py"]
#CMD ["sleep","infinity"]