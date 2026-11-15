[Help centre](../README.md) · Fix a problem · troubleshooting
<!-- help: fix / problems -->

# A plug-in will not add

When Starboard will not add a plug-in from the collection, the message on the **Catalogue** page says why. Find it
here.

```flow
title: Find your answer
start: A plug-in will not add
q: What does Starboard say?
  It needs a newer plug-in API -> 1
  No access to Docker here -> 2
  This plug-in cannot be added -> 3
  The file changed since the catalogue listed it -> 4
1: Update Starboard #1-update-starboard
2: Give Starboard access to Docker #2-give-starboard-access-to-docker
3: Read the test results #3-read-the-test-results
4: Try again tomorrow #4-try-again-tomorrow
```

## 1. Update Starboard

Every plug-in here needs plug-in API 1.14, in Starboard 0.18.0 or later, and Library clean-up needs plug-in API 1.15,
in Starboard 0.19.0 or later. An older Starboard is offered each plug-in's version before, from the catalogue, except
Library clean-up, which has no earlier version. Read
[Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## 2. Give Starboard access to Docker

Plug-ins that run containers need it. Styles does not. Read
[Change what Starboard can access](https://themightytrex.github.io/starboard/help/topics/change-what-starboard-can-access.html).

## 3. Read the test results

Starboard tests every plug-in before it is added. The results under the message say what is wrong and how to fix it.
Tell its maker, at the [plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## 4. Try again tomorrow

The catalogue and the file do not match, so Starboard did not use it. Starboard reads the catalogue at most once a
day: try again the next day.

## Find out more

- [Add your first plug-in](../start/add-your-first-plug-in.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
