"""One-time explainers for the television words people meet first (DASH-642, owner 28 November 2026).

Each term has a notice with a plain meaning. A person dismisses it once and it never shows again, on any page. What was
dismissed is kept with the station's other state, as a list of ids under "explained", so nothing runs and nothing is
asked while idle. The plain words are in the glossary of the design research (mockups/tv-channel-settings-2026-11-28).
"""
PREFIX = "explain:"

TERMS = {
    "short-title-clip": ("What is a short title clip?",
                         "It is a few seconds of video that shows your station name, played between programmes. TV people call it an ident."),
    "coming-up-trailer": ("What is a coming-up trailer?",
                          "It is a short trailer for a programme that is coming up. The plug-in makes them for you when nobody is watching. "
                          "TV people call it a promo."),
    "waiting-screen": ("What is a waiting screen?",
                       "It is a picture or short video that loops, with a countdown, until the next programme starts. "
                       "TV people call it a holding slide."),
    "branding": ("What is branding?",
                 "It is a logo, title clips, cards and music made to go together. A branding file is a zip made from the template. "
                 "TV people call it a broadcast pack."),
    "title-bar": ("What is a title bar?",
                  "It is the line of words that names the programme when it starts, or says what is on next. TV people call it a strap."),
    "own-short-video": ("What is a short video of your own?",
                        "It is a video you add yourself, such as a message or a clip, that plays in a break. "
                        "TV people call it an advert."),
}

# Which terms each page shows, at most two at a time so a page is never crowded.
PAGES = {
    "clips": ("short-title-clip", "waiting-screen", "coming-up-trailer"),
    "channels": ("short-title-clip", "coming-up-trailer", "waiting-screen"),
    "pack": ("branding", "title-bar", "coming-up-trailer"),
    "grids": ("own-short-video", "short-title-clip"),
}
MOST = 2


def dismissed(state):
    got = state.get("explained")
    return set(got) if isinstance(got, list) else set()


def notices(state, page):
    """The explainers still to show on a page: notices Starboard draws with a Dismiss button."""
    done = dismissed(state)
    out = []
    for term in PAGES.get(page, ()):
        if term not in done and term in TERMS:
            title, text = TERMS[term]
            out.append({"id": PREFIX + term, "tone": "info", "title": title, "text": text, "dismiss": True})
        if len(out) >= MOST:
            break
    return out


def dismiss(state, rid):
    """Records a dismissed explainer. True when rid was one, so the caller need do nothing else."""
    if not str(rid).startswith(PREFIX):
        return False
    term = str(rid)[len(PREFIX):]
    if term in TERMS:
        done = sorted(dismissed(state) | {term})
        state["explained"] = done
    return True
