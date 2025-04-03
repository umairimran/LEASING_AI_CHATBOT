# Multi-Embedding Document Chatbot

## Installation and Setup Guide

### Prerequisites

1. **Install Docker**
   - Download and install Docker from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
   - Follow the installation instructions for your operating system

### Running the Application

1. **Start Docker**
   - Open Docker Desktop on your computer
   - Ensure Docker is running properly (check for the Docker icon in your system tray)

2. **Start the Backend Services**
   - Open a terminal/command prompt
   - Navigate to the project root directory
   - Run the following command:
     ```
     docker-compose up -d
     ```
   - This will start all the required services (Weaviate, Backend API, etc.)
   - This process may take a few minutes to complete

3. **Launch the Frontend**
   - Once the backend services are running, open a new terminal
   - Navigate to the Frontend directory:
     ```
     cd Frontend
     ```
   - Start the Streamlit application:
     ```
     streamlit run app.py
     ```
   - The application will start and automatically open in your default web browser

4. **Your chatbot is now ready to use!**
   - Upload documents and start chatting with them

Task accompolished.