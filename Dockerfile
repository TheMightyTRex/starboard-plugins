# Every example plug-in in one small image (Python's standard library only), so Starboard downloads it once.
# Each manifest chooses its app with the EXAMPLE environment setting (run.py starts /app/<EXAMPLE>/app.py). Built and published by .github/workflows/image.yml.
FROM python:3.12-alpine
# Every package of the base image takes Alpine's fixed version at build (as Starboard does), so a fix such as
# zlib's CVE-2026-4738 or krb5's 1.22.3 reaches the next build with no change here.
RUN apk upgrade --no-cache
WORKDIR /app
COPY _shared/sbplugin.py _shared/run.py /app/
COPY audio-description/app.py audio-description/rules.json /app/audio-description/
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
# The Python modules the app imports, compiled once here: the container's file system is read only, so otherwise
# every start compiles them again (measured 16 November 2026: start 0.71 to 0.15 processor seconds, first answer
# 0.9 to 0.4 seconds, 0.6 MB less memory at rest, for about 3 MB more image).
RUN python3 -c "import modulefinder, py_compile, sys; f = modulefinder.ModuleFinder(path=['/app'] + sys.path); [f.run_script(p) for p in sys.argv[1:]]; [py_compile.compile(m.__file__, doraise=True) for m in f.modules.values() if (m.__file__ or '').endswith('.py')]" /app/*/app.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
USER 10001:10001
CMD ["python3", "/app/run.py"]
