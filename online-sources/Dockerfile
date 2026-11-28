# Online sources: Python's standard library only. Built by Starboard from this zip (a private draft: not in the catalogue, no image is published).
FROM python:3.12-alpine
RUN apk upgrade --no-cache
WORKDIR /app
COPY sbplugin.py app.py /app/
# The Python modules the app imports, compiled once here: the container's file system is read only.
RUN python3 -c "import modulefinder, py_compile, sys; f = modulefinder.ModuleFinder(path=['/app'] + sys.path); [f.run_script(p) for p in sys.argv[1:]]; [py_compile.compile(m.__file__, doraise=True) for m in f.modules.values() if (m.__file__ or '').endswith('.py')]" /app/app.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
