# Jellystat plug-in helper: Python's standard library on the same PostgreSQL image as the database container, so
# psql and pg_restore match the server's version. The base is pinned by digest.
FROM postgres:15-alpine@sha256:fc41cfa8a90c09e84dd723ee764be4b2f59ba6c98b1e5b3fca540adddf68a5ba
# Every package of the base image takes Alpine's fixed version at build (as Starboard does), so a fix such as
# zlib's CVE-2026-4738 or krb5's 1.22.3 reaches the next build with no change here.
RUN apk upgrade --no-cache
RUN apk add --no-cache python3
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 70:70
ENTRYPOINT []
CMD ["python3", "/app/app.py"]
