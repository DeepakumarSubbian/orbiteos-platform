FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    pymodbus \
    paho-mqtt

COPY . /app

CMD ["python", "simulator.py"]
