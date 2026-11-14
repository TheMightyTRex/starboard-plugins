# Direct play: Python's standard library, ffmpeg (ffprobe included) from Alpine to probe and convert films and
# series, and tzdata so weekends and quiet hours are in the server's own time zone.
# Built and published by .github/workflows/direct-play-image.yml.
FROM python:3.12-alpine
# Every package of the base image takes Alpine's fixed version at build (as Starboard does), so a fix reaches the next
# build with no change here.
RUN apk upgrade --no-cache
RUN apk add --no-cache ffmpeg tzdata
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
