# SPDX-License-Identifier: MIT
# Starboard's start-up for Calibre-Web (plug-in version 1.2.0). Starboard writes this file once into the plug-in's own
# data folder, and the container runs it instead of Calibre-Web's own start. It sets up Calibre-Web before the first
# start, with nothing typed by hand, and then starts Calibre-Web itself.
#
# First start only (no app.db yet): Calibre-Web makes its own settings database, the admin password is replaced by
# the one Starboard made (it arrives in the environment, is never printed and is never put on a command line), uploads
# and public sign-up stay off, and editing and deleting are off for the admin because the books folder is read only.
# Every start: if Calibre-Web has no library yet and one is there, it is set (a library Starboard built, or one that
# was already in the books folder). A library you chose yourself in Calibre-Web is never changed.
import contextlib
import io
import os
import runpy
import sqlite3
import sys

CONFIG = os.environ.get("CALIBRE_DBPATH", "/config")
DB = os.path.join(CONFIG, "app.db")
DONE = os.path.join(CONFIG, "starboard-first-sign-in.done")
APP = "/app/calibre-web"
# Where a Calibre library may be, first choice first: the one Starboard builds, then the books folder itself.
LIBRARIES = ("/media/books-library", "/media/books")
ROLE_UPLOAD, ROLE_EDIT, ROLE_DELETE = 1 << 2, 1 << 3, 1 << 7


def library():
    for folder in LIBRARIES:
        if os.path.isfile(os.path.join(folder, "metadata.db")):
            return folder
    return ""


def first_start():
    """Calibre-Web's own code makes app.db when it is imported (-s with a name that is not there makes it and stops
    at once, with nothing started), so the file has exactly the shape this version of Calibre-Web expects."""
    saved = sys.argv
    sys.argv = ["cps.py", "-p", DB, "-s", "nobody:x"]
    sys.path.insert(0, APP)
    try:
        with contextlib.redirect_stdout(io.StringIO()):  # it says the name is not valid, which is the point
            runpy.run_path(os.path.join(APP, "cps.py"), run_name="__main__")
    except SystemExit:
        pass
    finally:
        sys.argv = saved
        for name in [n for n in sys.modules if n == "cps" or n.startswith("cps.")]:
            del sys.modules[name]
        try:
            sys.path.remove(APP)
        except ValueError:
            pass
    return os.path.exists(DB)


def set_password(con, password):
    """The hash Calibre-Web itself makes. Its sign-in rules about letters and symbols apply to a password typed in
    Calibre-Web, not to a long random one made here."""
    from werkzeug.security import generate_password_hash
    con.execute("update user set password = ? where name = 'admin'", (generate_password_hash(password),))


def settings(first, password=""):
    con = sqlite3.connect(DB, timeout=30)
    try:
        row = con.execute("select id, config_calibre_dir from settings order by id limit 1").fetchone()
        if row is None:
            return
        fields, values = [], []
        if first:
            # uploads, public sign-up, anonymous browsing and remote login stay off; Kobo sync is not used
            for name in ("config_uploading", "config_public_reg", "config_anonbrowse", "config_remote_login", "config_kobo_sync"):
                fields.append(name + " = ?")
                values.append(0)
        current = row[1] or ""
        found = library()
        if found and not os.path.isfile(os.path.join(current, "metadata.db")):
            fields.append("config_calibre_dir = ?")
            values.append(found)
        if fields:
            con.execute("update settings set " + ", ".join(fields) + " where id = ?", values + [row[0]])
        if first:
            set_password(con, password)
            con.execute("update user set role = role & ? where name = 'admin'", (~(ROLE_UPLOAD | ROLE_EDIT | ROLE_DELETE) & 0xFFFF,))
        con.commit()
    finally:
        con.close()


def let_starboard_look():
    """Starboard runs as another user and cannot open this folder (it is 700, for the user Calibre-Web runs as), so it
    could not tell that the password was set. 711 lets it check that one named file is there, and nothing more: the
    plug-in's own folder above this one is closed to everyone but Starboard."""
    try:
        os.chmod(CONFIG, 0o711)
    except OSError:
        pass


def stop(words):
    print("Starboard: " + words, flush=True)
    sys.exit(1)


def main():
    password = os.environ.pop("STARBOARD_ADMIN_PASSWORD", "")
    if not os.path.exists(DB):
        # Never start with Calibre-Web's own default password: without a password to set, or if setting it fails,
        # stop and say so, and remove the half-made settings so the next start tries again.
        if not password:
            stop("Calibre-Web was not started: Starboard gave it no password to set, and it will not start with its default one.")
        if not first_start():
            try:
                os.remove(DB)
            except OSError:
                pass
            stop("Calibre-Web was not started: its first set-up did not finish, so it will try again at the next start.")
        try:
            settings(True, password)
        except Exception as err:
            os.remove(DB)
            stop("Calibre-Web was not started: its settings could not be written (" + type(err).__name__ + ").")
        with open(DONE, "w") as marker:
            marker.write("done\n")
        let_starboard_look()
        print("Starboard: Calibre-Web is set up. Its first sign-in is on the plug-in's page in Starboard.", flush=True)
    else:
        if os.path.exists(DONE):
            let_starboard_look()  # Starboard makes the folder 700 again each time it starts the plug-in
        try:
            settings(False)
        except sqlite3.Error as err:
            print("Starboard: could not look at Calibre-Web's settings (" + type(err).__name__ + ").", flush=True)
    os.chdir(APP)
    sys.argv = ["cps.py"]
    sys.path.insert(0, APP)
    os.execv(sys.executable, [sys.executable, os.path.join(APP, "cps.py")])


if __name__ == "__main__":
    main()
