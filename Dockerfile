# Use the official Python image from the Docker Hub
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY . .

# Expose the port that Flask will run on
EXPOSE 5000

# Define the environment variable for Flask
ENV FLASK_APP=main.py

# Run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
