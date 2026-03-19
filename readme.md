# LEASING AI CHATBOT

A Docker-based AI chatbot application for leasing assistance.

## Prerequisites

- Docker Desktop
  - For Windows users: [Download Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
  - For Mac users: [Download Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/)
  - For Linux users: [Download Docker Desktop for Linux](https://docs.docker.com/desktop/install/linux-install/)

## First-Time Setup

1. Install Docker Desktop according to your operating system (using links above)
2. Start Docker Desktop and ensure it's running
3. Extract the project files(Chatbot) to your desired location
4. Open a terminal/command prompt
5. Navigate to the project directory:
   ```
   cd path/to/LEASING_AI_CHATBOT
   ```
6. Run the following command to start the application:
   ```
   docker compose up -d
   ```
   > Note: The first-time setup may take several minutes as it downloads and builds the necessary containers.

7. Once the setup is complete, open your web browser and visit:
   ```
   
   ```

## Regular Usage

After the initial setup, follow these steps to start the chatbot:

1. Start Docker Desktop
2. Open a terminal/command prompt
3. Navigate to the project directory
4. Run:
   ```
   docker compose up -d
   ```
5. Visit `http://127.0.0.1:8501/` in your web browser

## Troubleshooting

If you encounter any errors during startup:
1. Press `Ctrl+C` to stop the current process
2. Try running the `docker compose up -d` command again
3. Ensure Docker Desktop is running properly
4. Check if port 8501 is not being used by another application

## Support

If you need assistance, please contact me.