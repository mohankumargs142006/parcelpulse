FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 appuser
RUN mkdir -p /data/archive && chown -R appuser:appuser /data
COPY parcelpulse ./parcelpulse
USER appuser
EXPOSE 8000 9101
CMD ["uvicorn", "parcelpulse.api:app", "--host", "0.0.0.0", "--port", "8000"]
