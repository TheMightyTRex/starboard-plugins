[Help centre](../README.md) · Developers · how-to
<!-- help: dev / ai -->

# Make a plug-in with an AI assistant

An AI assistant can write a plug-in for plug-in API 1.17 if you give it the rules. Starboard's help has a prompt for
each kind of plug-in in the collection.

## Before you begin

- An AI assistant you already use.
- Starboard's help is the final word. If the assistant says something different, follow the help.

## Steps

1. Open [AI prompts for developers, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/ai-prompts-for-developers.html).
2. Choose the prompt for what you want to make: a card plug-in, an app plug-in, or a plug-in that converts files,
   like Direct play.
3. Copy it, fill in the parts in square brackets, and paste the pages it names under it.
4. Test what comes back with Starboard's plug-in tester, then with `tools/check_help.py` for its help pages.

## Things to note

- Each prompt carries a checklist the assistant must follow: permissions, memory limits, accessibility, updates,
  card refresh times and the content rules.
- For a plug-in in this repository, also give it [Plug-in API 1.15 for the collection](plug-in-api.md) and
  [Direct play's card, worked through](a-card-worked-through.md).
- Starboard's help centre has a plain list of its developer pages for AI tools, `llms.txt`.

## Find out more

- [Make a plug-in for the collection](make-a-plug-in-for-the-collection.md)
- [Plug-in API 1.15 for the collection](plug-in-api.md)
