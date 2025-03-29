# Use a Python base image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the content of the local directory to the container's /app directory
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that FastAPI will run on
EXPOSE 8000

# Command to run the app
CMD ["uvicorn", "Backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
