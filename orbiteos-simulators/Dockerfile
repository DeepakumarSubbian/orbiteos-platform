FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy simulator code
COPY src/ ./src/

# Expose Modbus TCP port
EXPOSE 502

# Expose MQTT monitoring port (optional)
EXPOSE 1883

# Run the main simulator orchestrator
CMD ["python", "-u", "src/main.py"]
