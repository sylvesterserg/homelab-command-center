FROM python:3.12-slim

RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY server.py /app/server.py
RUN mkdir -p /data && chown app:app /data /app

USER app
ENV PORT=8741 HOST=0.0.0.0 DATA_DIR=/data
EXPOSE 8741

CMD ["python3", "/app/server.py"]
