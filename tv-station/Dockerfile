# Create your own TV channel: Python's standard library, FFmpeg (it draws the on-screen logo and the cards, makes the stream,
# checks broadcast packs and makes the promos and the example pack) and
# tzdata, so times on screen and in the guide are the server's own; eSpeak NG, the voice for audio description on promos
# (0.7.0: about 6 MB more, measured 22 November 2026, 68.9 MB to 74.9 MB unpacked on amd64). Built and published by
# .github/workflows/tv-station-image.yml for amd64, arm64 and arm/v7.
FROM alpine:3.21
# Every package takes Alpine's fixed version at build, so a fix reaches the next build with no change here.
RUN apk upgrade --no-cache && apk add --no-cache python3 ffmpeg tzdata espeak-ng
WORKDIR /app
COPY sbplugin.py app.py schedule.py guide.py dog.py animate.py played.py breaks.py three_d.py stream.py library.py pack.py promo.py example_pack.py grid.py suggest.py tv_words.py titles.py speak.py breakgrid.py filelist.py flash.py draw.py kit.py handoff.py recipes.py stylepage.py pack.schema.json grid.html grid.js grid.css breaks.html breaks.js breaks.css files.html files.js files.css style.html style.js style.css ds-tokens.css ds-components.css /app/
COPY atkinson-hyperlegible-next.woff2 LICENSE-OFL.txt /app/
# The Python modules the app imports, compiled once here: the container's file system is read only, so otherwise
# every start compiles them again (measured 16 November 2026 on the other plug-ins: start 0.71 to 0.15 processor seconds).
RUN python3 -c "import modulefinder, py_compile, sys; f = modulefinder.ModuleFinder(path=['/app'] + sys.path); [f.run_script(p) for p in sys.argv[1:]]; [py_compile.compile(m.__file__, doraise=True) for m in f.modules.values() if (m.__file__ or '').endswith('.py')]" /app/app.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
EXPOSE 8080
CMD ["python3", "/app/app.py"]
