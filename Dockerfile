# 1. Base Image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Set environment variables untuk logging Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 4. Buat non-root user 'appuser'
RUN adduser --disabled-password --gecos '' appuser

# 5. Instal dependencies
# Copy hanya requirements.txt dulu untuk caching layer
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy sisa kode aplikasi
COPY ./src ./src

# 7. Buat folder untuk data persisten (SQLite)
# dan berikan kepemilikan ke appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# 8. Ganti ke non-root user
USER appuser

# 9. Expose port yang digunakan Uvicorn
EXPOSE 8080

# 10. Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]