FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    pymodbus \
    paho-mqtt \
    schedule \
    numpy

# Copy simulator code
COPY . /app

# Run simulator
CMD ["python", "simulator.py"]
