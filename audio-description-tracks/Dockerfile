# Audio description tracks: Python's standard library and mkvmerge (MKVToolNix) from Alpine, to copy a sound track into
# a Matroska file without converting it and read exact lengths. MKVToolNix keeps the image at 146 MB; ffmpeg made it
# 261 MB (measured 13 November 2026). Nothing is pushed from here.
FROM python:3.12-alpine
RUN apk add --no-cache mkvtoolnix
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
