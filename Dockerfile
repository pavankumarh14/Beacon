# One service runs both parts of Beacon: server.py serves the browser UI from
# web/ and exposes the JSON API used by that UI.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    BEACON_DB=/var/data/beacon.db

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Render mounts its persistent disk here. Creating it also makes local Docker
# runs work when no Render disk is attached.
RUN mkdir -p /var/data

EXPOSE 10000

CMD ["python", "server.py"]
