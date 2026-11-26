"""Calibre-Web 1.2.0 (DASH-590, owner, 26 November 2026: "is it picking up the ebook library? If not it should be
configured during install automatically"): its start-up sets it up before the first start, with a generated password
Starboard shows once, a library found by itself, uploads off, and never the default password."""
import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, STARBOARD_SRC, manifest  # noqa: E402

START = os.path.join(ROOT, "calibre-web", "start.py")


def load_start(config):
    spec = importlib.util.spec_from_file_location("calibre_web_start", START)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.CONFIG = config
    mod.APP = config  # a folder that is there, in place of Calibre-Web's own
    mod.DB = os.path.join(config, "app.db")
    mod.DONE = os.path.join(config, "starboard-first-sign-in.done")
    return mod


def make_app_db(path, library=None):
    """The part of Calibre-Web's app.db the start-up touches, as Calibre-Web makes it on first import."""
    con = sqlite3.connect(path)
    con.execute("create table settings (id integer primary key, config_calibre_dir text, config_uploading integer default 1, "
                "config_public_reg integer default 1, config_anonbrowse integer default 1, config_remote_login integer default 1, config_kobo_sync integer default 1)")
    con.execute("create table user (id integer primary key, name text, role integer, password text)")
    con.execute("insert into settings (id, config_calibre_dir) values (1, ?)", (library,))
    con.execute("insert into user (name, role, password) values ('admin', 339, 'default-hash')")
    con.execute("insert into user (name, role, password) values ('Guest', 32, '')")
    con.commit()
    con.close()


class FakeWerkzeug:
    def __enter__(self):
        security = types.ModuleType("werkzeug.security")
        security.generate_password_hash = lambda p: "hash:" + p[::-1]
        self.patch = mock.patch.dict(sys.modules, {"werkzeug": types.ModuleType("werkzeug"), "werkzeug.security": security})
        self.patch.start()

    def __exit__(self, *a):
        self.patch.stop()


class StartUp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = os.path.join(self.tmp.name, "config")
        os.makedirs(self.config)
        self.mod = load_start(self.config)
        self.books = os.path.join(self.tmp.name, "books")
        self.library = os.path.join(self.tmp.name, "books-library")
        self.mod.LIBRARIES = (self.library, self.books)
        self.db = self.mod.DB

    def tearDown(self):
        self.tmp.cleanup()

    def row(self, sql):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()

    def library_in(self, folder):
        os.makedirs(folder, exist_ok=True)
        open(os.path.join(folder, "metadata.db"), "w").close()

    def test_the_first_start_sets_the_password_and_closes_what_should_be_closed(self):
        make_app_db(self.db)
        with FakeWerkzeug():
            self.mod.settings(True, "a-long-generated-password")
        self.assertEqual(self.row("select password from user where name = 'admin'"), [("hash:drowssap-detareneg-gnol-a",)])
        self.assertEqual(self.row("select config_uploading, config_public_reg, config_anonbrowse, config_remote_login, config_kobo_sync from settings"), [(0, 0, 0, 0, 0)])
        role = self.row("select role from user where name = 'admin'")[0][0]
        self.assertEqual(role & (1 << 2 | 1 << 3 | 1 << 7), 0)  # no upload, edit or delete
        self.assertTrue(role & 1)  # still an admin
        self.assertEqual(self.row("select password from user where name = 'Guest'"), [("",)])

    def test_the_library_starboard_made_is_used_before_the_books_folder(self):
        make_app_db(self.db)
        self.library_in(self.books)
        self.library_in(self.library)
        self.mod.settings(False)
        self.assertEqual(self.row("select config_calibre_dir from settings"), [(self.library,)])

    def test_a_library_already_in_the_books_folder_is_found(self):
        make_app_db(self.db)
        self.library_in(self.books)
        self.mod.settings(False)
        self.assertEqual(self.row("select config_calibre_dir from settings"), [(self.books,)])

    def test_no_library_changes_nothing(self):
        make_app_db(self.db)
        self.mod.settings(False)
        self.assertEqual(self.row("select config_calibre_dir from settings"), [(None,)])

    def test_a_library_the_person_chose_that_still_works_is_never_changed(self):
        mine = os.path.join(self.tmp.name, "mine")
        self.library_in(mine)
        self.library_in(self.library)
        make_app_db(self.db, mine)
        self.mod.settings(False)
        self.assertEqual(self.row("select config_calibre_dir from settings"), [(mine,)])

    def test_later_starts_leave_the_password_and_choices_alone(self):
        make_app_db(self.db)
        self.mod.settings(False)
        self.assertEqual(self.row("select password from user where name = 'admin'"), [("default-hash",)])
        self.assertEqual(self.row("select config_uploading from settings"), [(1,)])  # the person may have turned it on

    def test_it_refuses_to_start_without_a_password_and_leaves_no_settings(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STARBOARD_ADMIN_PASSWORD", None)
            with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()) as said:
                self.mod.main()
        self.assertEqual(stop.exception.code, 1)
        self.assertIn("default one", said.getvalue())
        self.assertFalse(os.path.exists(self.db))

    def test_a_failed_first_set_up_removes_the_half_made_settings(self):
        def broken():
            make_app_db(self.db)
            return True
        with mock.patch.dict(os.environ, {"STARBOARD_ADMIN_PASSWORD": "secret-value-xyz"}), mock.patch.object(self.mod, "first_start", broken), \
                mock.patch.object(self.mod, "settings", side_effect=sqlite3.OperationalError("locked")), \
                self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as said:
            self.mod.main()
        self.assertFalse(os.path.exists(self.db))
        self.assertNotIn("secret-value-xyz", said.getvalue())

    def test_the_password_is_taken_out_of_the_environment_and_never_printed(self):
        calls = []

        def first():
            make_app_db(self.db)
            return True
        with mock.patch.dict(os.environ, {"STARBOARD_ADMIN_PASSWORD": "secret-value-xyz"}), mock.patch.object(self.mod, "first_start", first), \
                mock.patch.object(self.mod.os, "execv", lambda *a: calls.append((a, dict(os.environ)))), FakeWerkzeug(), \
                contextlib.redirect_stdout(io.StringIO()) as said:
            self.mod.main()
        self.assertNotIn("secret-value-xyz", said.getvalue())
        self.assertNotIn("STARBOARD_ADMIN_PASSWORD", calls[0][1])  # Calibre-Web never gets it
        self.assertNotIn("secret-value-xyz", " ".join(calls[0][0][1]))
        self.assertTrue(os.path.exists(self.mod.DONE))

    def test_starboard_can_check_the_done_file_but_not_list_the_folder(self):
        """Starboard runs as another user and Calibre-Web's data folder is 700, so without this it could not tell that the
        password was set (found on the real install's permissions, 26 November 2026)."""
        os.chmod(self.config, 0o700)
        make_app_db(self.db)
        open(self.mod.DONE, "w").close()
        with mock.patch.object(self.mod.os, "execv", lambda *a: None), contextlib.redirect_stdout(io.StringIO()):
            self.mod.main()
        self.assertEqual(os.stat(self.config).st_mode & 0o777, 0o711)

    def test_it_starts_calibre_web_itself_on_an_old_install_with_no_password(self):
        make_app_db(self.db)
        calls = []
        with mock.patch.object(self.mod.os, "execv", lambda *a: calls.append(a)), contextlib.redirect_stdout(io.StringIO()):
            self.mod.main()  # app.db is there: the person's own password stays, nothing is refused
        self.assertEqual(len(calls), 1)
        self.assertFalse(os.path.exists(self.mod.DONE))


class Manifest(unittest.TestCase):
    def setUp(self):
        self.m = manifest("calibre-web")
        self.app = self.m["containers"][0]

    def test_the_start_up_in_the_manifest_is_the_file(self):
        with open(START, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(self.app["files"], {"starboard-start-1.py": text})
        self.assertEqual(self.app["entrypoint"], ["/lsiopy/bin/python3", "/config/starboard-start-1.py"])
        self.assertLessEqual(len(text), 16384)
        self.assertNotIn("admin123", text)

    def test_the_password_is_a_secret_shown_once_and_needs_the_api_that_shows_it(self):
        self.assertEqual(self.app["env"]["STARBOARD_ADMIN_PASSWORD"], "{secret:admin_password}")
        self.assertEqual(self.m["first_sign_in"], {"user": "admin", "secret": "admin_password", "ready_file": "app/starboard-first-sign-in.done"})
        self.assertEqual(self.m["starboard_api"], ">=1.20 <2.0")
        with open(START, encoding="utf-8") as f:
            self.assertIn("starboard-first-sign-in.done", f.read())

    def test_the_books_stay_read_only_and_the_library_folder_too(self):
        self.assertEqual(self.app["volumes"], ["data:/config", "media/books:ro", "media/books-library:ro"])
        self.assertEqual(self.m["permissions"], ["network:lan", "network:port"])

    def test_the_old_version_is_kept_for_an_older_starboard(self):
        with open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8") as f:
            entry = next(e for e in json.load(f)["plugins"] if e["id"] == "calibre-web")
        self.assertEqual([v["version"] for v in entry["versions"]], ["1.2.1", "1.1.1", "1.0.0"])
        self.assertEqual(entry["versions"][1]["starboard_api"], ">=1.14 <2.0")
        self.assertTrue(entry["versions"][1]["manifest_sha256"])

    def test_it_passes_starboards_own_check(self):
        if not os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")):
            self.skipTest("Starboard's source is not here (STARBOARD_SRC)")
        sys.path.insert(0, STARBOARD_SRC)
        from starboard import plugins
        if not plugins._range_ok(">=1.20"):
            self.skipTest("this Starboard is older than plug-in API 1.20")
        self.assertEqual(plugins.check(self.m), [])


if __name__ == "__main__":
    unittest.main()
