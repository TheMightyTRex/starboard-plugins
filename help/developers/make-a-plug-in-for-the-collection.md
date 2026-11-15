[Help centre](../README.md) · Developers · how-to
<!-- help: dev / build -->

# Make a plug-in for the collection

Add a new plug-in to this repository, from its folder to its help pages and its place in the catalogue. At the end
it is tested, listed and ready to publish.

## Before you begin

- A copy of [the starboard-plugins repository](https://github.com/TheMightyTRex/starboard-plugins) and of
  [Starboard](https://github.com/TheMightyTRex/starboard), for the plug-in tester.
- Python 3, and Docker to build and smoke-test an image.
- Read [Plug-in API 1.14 for the collection](plug-in-api.md).

## Steps

1. Make a folder named after its id, such as `disk-forecast`, with `starboard-plugin.json`, `README.md`,
   `LICENSE` and `install.py` (copy `LICENSE` and `install.py` from Styles).
2. For a small card plug-in, add it to `tools/examples_src.py` instead, and run `tools/make_examples.py`: it
   writes the folder, the README and the changelog from one place, on the shared image.
3. Draw its logo: add it to `tools/make_logos.py` and run it. Every logo is a rounded tile in one colour, with a
   white symbol and at least 4.5 to 1 contrast.
4. Test it with Starboard's plug-in tester, from your Starboard copy:

   ```bash
   python3 -m starboard.plugin_tester <path to>/starboard-plugin.json
   ```

5. Add tests in `tests/`, and run them all:

   ```bash
   python3 -m unittest discover -s tests
   ```

6. Run the smoke test, which runs each image hardened, as Starboard does, against stand-ins:

   ```bash
   STARBOARD_SRC=<your Starboard copy> python3 tools/smoke_test.py
   ```

7. Write its help: put it in one group in `help-centre.json`, under `plugins`, and write its seven pages in
   `help/plugins/<id>/`. Then check them:

   ```bash
   python3 tools/check_help.py
   ```

8. Pin its image by digest once GitHub has built it, then run `tools/make_examples.py` (it writes `catalogue.json`)
   and `tools/make_zips.py`.

## Things to note

- A plug-in is listed as published only when every image it runs is pinned by digest, or it runs none.
- The help centre is built from `help/` and each README by the design system's builder, and published when `main`
  changes. A page left as a placeholder stops the build.

## Find out more

- [Card plug-ins: Direct play's card, worked through](a-card-worked-through.md)
- [App plug-ins](app-plug-ins.md)
- [Test and publish a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/test-and-publish-a-plugin.html)
