# Every example plug-in in one small image (Python's standard library only), so Starboard downloads it once.
# Each manifest chooses its app with the EXAMPLE environment setting (run.py starts /app/<EXAMPLE>/app.py). Built and published by .github/workflows/image.yml.
FROM python:3.12-alpine
WORKDIR /app
COPY _shared/sbplugin.py _shared/run.py /app/
COPY disk-forecast/app.py /app/disk-forecast/
COPY dns-blocking/app.py /app/dns-blocking/
COPY download-summary/app.py /app/download-summary/
COPY home-assistant/app.py /app/home-assistant/
COPY library-health/app.py /app/library-health/
COPY line-speed/app.py /app/line-speed/
COPY most-watched/app.py /app/most-watched/
COPY notifications/app.py /app/notifications/
COPY outside-services/app.py /app/outside-services/
COPY vpn-check/app.py /app/vpn-check/
COPY watch-stats/app.py /app/watch-stats/
COPY watching-now/app.py /app/watching-now/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
USER 10001:10001
CMD ["python3", "/app/run.py"]
