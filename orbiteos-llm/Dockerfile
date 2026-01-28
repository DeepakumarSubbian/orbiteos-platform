FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Expose chat interface port
EXPOSE 9000

# Run the LLM agent
CMD ["python", "-m", "uvicorn", "src.agent:app", "--host", "0.0.0.0", "--port", "9000"]
