FROM python:3.11-slim

WORKDIR /app

# WeasyPrint system dependencies (cairo, pango, ffi). gdk-pixbuf is no longer
# required in WeasyPrint >= 53 — it uses Pillow for raster images now.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

