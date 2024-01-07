# Use an official Python runtime as a parent image
FROM python:3.9.5-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

RUN apt-get update && apt-get -y install libpq-dev gcc

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

ENTRYPOINT ["gunicorn"]

# Run app.py when the container launches
CMD ["-w", "1", "-b", "0.0.0.0:5000", "app:app"]