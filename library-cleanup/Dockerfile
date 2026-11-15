# Library clean-up: Python's standard library only, from Alpine, and tzdata so its times are the server's own.
# Built and published by .github/workflows/library-cleanup-image.yml.
FROM alpine:3.21
# Every package takes Alpine's fixed version at build, so a fix reaches the next build with no change here.
RUN apk upgrade --no-cache && apk add --no-cache python3 tzdata
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
