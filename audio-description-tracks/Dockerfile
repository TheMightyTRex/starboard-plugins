# Audio description tracks: Python's standard library and mkvmerge (MKVToolNix) from Alpine, to copy a sound track into
# a Matroska file without converting it and read exact lengths. MKVToolNix keeps the image at 146 MB; ffmpeg made it
# 261 MB (measured 13 November 2026).
# Built and published by .github/workflows/audio-description-tracks-image.yml.
FROM python:3.12-alpine
# Every package of the base image takes Alpine's fixed version at build (as Starboard does), so a fix such as
# zlib's CVE-2026-4738 or krb5's 1.22.3 reaches the next build with no change here.
RUN apk upgrade --no-cache
RUN apk add --no-cache mkvtoolnix
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
