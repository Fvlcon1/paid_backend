FROM python:3.10-slim

# Install system dependencies (including libglib2.0 for OpenCV GTK support)
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libgl1 \
    libglib2.0-0 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the InsightFace model (runs after OpenCV is fully functional)
RUN python -c "import insightface; model = insightface.app.FaceAnalysis(); model.prepare(ctx_id=0, det_size=(640, 640))"

# Copy the rest of the app
COPY . .

# Expose the port
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
