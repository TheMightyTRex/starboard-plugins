# Picture shrinker: Python and Pillow from Alpine (built for every processor Alpine has, so no compiler is needed),
# and tzdata so the schedule is in the server's own time zone. Built and published by
# .github/workflows/picture-shrinker-image.yml.
FROM alpine:3.21
# Every package takes Alpine's fixed version at build, so a fix reaches the next build with no change here.
RUN apk upgrade --no-cache && apk add --no-cache python3 py3-pillow tzdata
WORKDIR /app
COPY sbplugin.py app.py rules.json /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
