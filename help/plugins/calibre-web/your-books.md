# Calibre-Web: Your books

Calibre-Web reads a Calibre library, not a folder of books. This page says what that means, how Starboard finds your library and how to make one from books you already have.

## What Calibre-Web needs

A Calibre library is a folder with a file called `metadata.db` in it, and one folder for each book. Calibre-Web reads `metadata.db` to list your books. A folder of book files, such as `Author/Title.epub`, has no `metadata.db`, so Calibre-Web shows nothing.

## How Starboard finds your library

Each time Calibre-Web starts, Starboard looks in your media folder:

1. `books-library`, the library [Calibre library maker](../calibre-library/install.md) makes.
2. `books`, in case your own Calibre library is already there.

The first one with `metadata.db` is set as Calibre-Web's library. If you chose a library yourself in Calibre-Web and it still works, Starboard leaves it alone.

## If you have a folder of books and no library

1. Add **Calibre library maker** from the **Catalogue**. It is small to keep: it rests when it is not used.
2. Go to **Settings**, then **Plug-ins**, then **Calibre library maker**. The page says how many books it found, how much room the library needs and how long it takes.
3. Select **Make the library**, read the question and select **Make the library** again. Your books folder is read only here and is never changed.
4. Watch the progress in words on the same page. A file that cannot be read is listed with the reason.
5. When it says **Done**, deactivate Calibre-Web and activate it again. It opens the new library.

When new books arrive in your books folder, run it again: it adds only what is new.

## Find out more

- [Install](install.md)
- [Problems](problems.md)
- [Calibre library maker](../calibre-library/install.md)
