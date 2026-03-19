# Use a Python base image
FROM python:3.10-slim

WORKDIR /app

# 1. Copy ONLY requirements first
COPY requirements.txt .

# 2. Normalize encoding (keep your fix)
RUN python -c "from pathlib import Path; p=Path('requirements.txt'); b=p.read_bytes(); \
import sys; \
data = (b.decode('utf-16') if b'\x00' in b[:200] else b.decode('utf-8', errors='replace')); \
p.write_text(data.replace('\\r\\n','\\n'), encoding='utf-8')"

# 3. Install dependencies (cached now ✅)
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy rest of your app
COPY . .

# Expose ports
EXPOSE 8000 8501  

# Run app
CMD ["bash", "-c", "uvicorn Backend.main:app --host 0.0.0.0 --port 8000 --reload & streamlit run Frontend/main.py --server.port 8501"]