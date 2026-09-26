FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY continuity ./continuity
COPY static ./static
COPY demo ./demo
COPY app.py .
RUN useradd --create-home --uid 10001 appuser && mkdir /app/.data && chown appuser:appuser /app/.data
USER appuser
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8765"]
