# Calibre library maker helper: Debian with Calibre's own command line tools (calibredb), and the small helper Starboard
# talks to. The base is pinned by digest. Calibre's package pulls in a web browser engine and graphics drivers that a
# command line tool never uses, so they are removed in the same step, which takes the image from about 1.2 GB to
# about 0.7 GB (measured 26 November 2026). calibredb is checked at the end of the build.
FROM debian:bookworm-slim@sha256:e67eeead736ff7bbe258ef088bff683635c561b1fcfefad0806c1df4ab49ce0e
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends calibre python3 \
 && dpkg --purge --force-depends libqt6webenginecore6 libqt6webengine6-data libqt6webenginecore6-bin python3-pyqt6.qtwebengine \
      libqt6webenginewidgets6 libqt6webengine6 libgl1-mesa-dri libllvm15 libz3-4 xdg-utils fonts-liberation2 optipng \
      libjpeg-turbo-progs libjxr-tools pyqt6-dev-tools python3-speechd \
 && apt-get clean && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man /usr/share/locale /var/cache/* \
 && QT_QPA_PLATFORM=offscreen HOME=/tmp calibredb --version
WORKDIR /app
COPY sbplugin.py app.py /app/
# The Python modules the app imports, compiled once here: the container's file system is read only, so otherwise
# every start compiles them again.
RUN python3 -c "import modulefinder, py_compile, sys; f = modulefinder.ModuleFinder(path=['/app'] + sys.path); [f.run_script(p) for p in sys.argv[1:]]; [py_compile.compile(m.__file__, doraise=True) for m in f.modules.values() if (m.__file__ or '').endswith('.py')]" /app/app.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen
USER 10001:10001
ENTRYPOINT []
CMD ["python3", "/app/app.py"]
