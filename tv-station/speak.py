"""The voice for audio description on promos (0.7.0, owner, 21 November 2026: "Can you add a task to add audio
description to promos"): the words on a promo, spoken, so a blind viewer hears what is coming and when.

Made on the server by eSpeak NG, a small speech program in the image (about 6 MB): nothing is sent anywhere, it has a
voice for each of the station's ten languages, and a promo's words take a few hundredths of a processor second. It runs
only while a promo is being made (quiet hours, one at a time, lowest priority), and only when Audio description on
promos is activated. The words go in on standard input, so no title can be read as an option.
"""
import os
import shutil
import subprocess
import wave

import tv_words

PROGRAM = "espeak-ng"
# eSpeak NG's voice for each station language (tv_words.TABLES). English is British, Portuguese is Portugal's.
VOICES = {"en": "en-gb", "fr": "fr-fr", "de": "de", "es": "es", "it": "it", "pt": "pt", "nl": "nl", "sv": "sv",
          "da": "da", "nb": "nb"}
SPEED = 160      # words a minute: a little slower than eSpeak NG's own 175, clearer over music
LONGEST = 400    # letters spoken at most
LIMIT = 20       # seconds eSpeak NG may take (it needs well under one)


def available():
    """True when the speech program is in the image."""
    return bool(shutil.which(PROGRAM))


def voice_of(lang):
    return VOICES[tv_words.code(lang)]


def clean(words):
    """One line of plain words: no control characters, nothing over LONGEST letters."""
    return " ".join("".join(c if c.isprintable() else " " for c in str(words or "")).split())[:LONGEST]


def command(lang, out):
    """The eSpeak NG command that reads standard input in the language's voice into a WAV file."""
    return [PROGRAM, "-v", voice_of(lang), "-s", str(SPEED), "--stdin", "-w", out]


def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def seconds_of(path):
    """How long a WAV file plays, or 0."""
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate() or 1)
    except (OSError, EOFError, wave.Error):
        return 0.0


def make(words, lang, out):
    """Speaks the words into `out` (a WAV file). Returns its length in seconds, or 0 when nothing was made."""
    words = clean(words)
    if not words or not available():
        return 0.0
    try:
        done = subprocess.run(command(lang, out), input=words.encode("utf-8"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=LIMIT, preexec_fn=_nice, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 0.0
    return seconds_of(out) if done.returncode == 0 else 0.0


def fitting(candidates, lang, folder, room):
    """The first of the candidates (longest first) whose speech fits in `room` seconds: {"file", "dur", "words"}, or
    None when none fits or nothing can be spoken."""
    for n, words in enumerate(candidates):
        out = os.path.join(folder, f"voice{n}.wav")
        dur = make(words, lang, out)
        if 0 < dur <= room:
            return {"file": out, "dur": round(dur, 2), "words": clean(words)}
    return None
