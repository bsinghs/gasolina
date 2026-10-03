FROM python:3.12-slim

WORKDIR /srv
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/api/ ./services/api/
COPY database/ ./database/

WORKDIR /srv/services/api
ENV PORT=8000
# Apply any new migrations, then start the API
CMD python -m scripts.migrate && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
