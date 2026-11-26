# Calibre-Web: Settings

Calibre-Web has no settings in Starboard to change. Starboard sets it up when it first starts, and everything else is set in the app itself, on its own page: open it with **Open Calibre-Web** on its tab.

## Its first sign-in

On its tab, **Its first sign-in** has **Show the password…**. It asks for your Starboard password and shows the password Starboard made for `admin` once. Afterwards the tab says when it was shown. Read [Install](install.md).

## Buttons

Calibre-Web's tab, in **Settings**, then **Plug-ins**, then **Calibre-Web**, has these buttons:

- **Open Calibre-Web** opens its own page in a new tab. It is there while it is active.
- **Activate** starts it, and Starboard chooses a free port for its page. **Deactivate** stops it and keeps its folder.
- **Try again** starts it again when it did not start.
- **Check for an update** is there when this Starboard is newer than the version was made for.
- **Remove Calibre-Web** stops it and takes it away. You choose where its folder goes; nothing is deleted.

## Things to note

- Calibre-Web can read only the `books` and `books-library` folders of your media folder, as `/media/books` and `/media/books-library`, and only to read.
- Uploading books and changing their details in Calibre-Web are off: Starboard gives it the folders read only. Add books to your books folder, then run [Calibre library maker](../calibre-library/install.md) again.
- Your phone's reading app can use OPDS at `/opds` on its page, with the `admin` sign-in.
- Calibre-Web keeps its users and choices in its own folder in Starboard's data, `data/plugins/calibre-web`.
- Its settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Your books](your-books.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
