"""The words drawn on the picture and written in the guide, in the station's language (0.6.0, owner, 21 November 2026:
"the create your own tv channel needs to have a language choice in the settings and it defaults to english").

Only the words a viewer meets are here: the straps, the cards, the label, the holding slide, the promos and the guide's
episode line. The plug-in's own pages stay in English, as Starboard does. Day and month names come from these tables,
never from the process's locale, and the clock is always 24-hour (HH:MM). English is exactly as it was before 0.6.0.
"""
import time

DEFAULT = "en"

# Each language: its words, then its day names (Monday first, as time.struct_time.tm_wday counts) and month names.
# "date_at" is a day more than a day away; "day_at" a day of the week that stays true all week (promos).
# Only languages whose letters are all in the bundled font (atkinson-hyperlegible-next.woff2, Latin-1 and a few more)
# are offered: drawtext has no fallback font, so Polish (ą, ę, ł, ś, ż) would draw gaps and is left out.
TABLES = {
    "en": {
        "name": "English", "today_at": "Today at {hm}", "tomorrow_at": "Tomorrow at {hm}",
        "date_at": "{wd} {d} {mon} at {hm}", "day_at": "{wd} at {hm}", "episode": "Series {s}, episode {e}", "sep": ": ",
        "up_next": "Up next at {hm}: {title}", "coming_up_next": "Coming up next", "later_on": "Later on {channel}",
        "coming_soon": "Coming soon", "live": "Live", "new": "New", "repeat": "Repeat", "back_soon": "Back soon",
        "next_in": "Next programme in ",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                   "November", "December"],
    },
    "fr": {
        "name": "Français", "today_at": "Aujourd'hui à {hm}", "tomorrow_at": "Demain à {hm}",
        "date_at": "{wd} {d} {mon} à {hm}", "day_at": "{wd} à {hm}", "episode": "Saison {s}, épisode {e}", "sep": " : ",
        "up_next": "À suivre à {hm} : {title}", "coming_up_next": "À suivre", "later_on": "Plus tard sur {channel}",
        "coming_soon": "Prochainement", "live": "En direct", "new": "Inédit", "repeat": "Rediffusion",
        "back_soon": "À tout de suite", "next_in": "Prochain programme dans ",
        "days": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                   "novembre", "décembre"],
    },
    "de": {
        "name": "Deutsch", "today_at": "Heute um {hm}", "tomorrow_at": "Morgen um {hm}",
        "date_at": "{wd}, {d}. {mon} um {hm}", "day_at": "{wd} um {hm}", "episode": "Staffel {s}, Folge {e}", "sep": ": ",
        "up_next": "Als Nächstes um {hm}: {title}", "coming_up_next": "Als Nächstes", "later_on": "Später auf {channel}",
        "coming_soon": "Demnächst", "live": "Live", "new": "Neu", "repeat": "Wiederholung",
        "back_soon": "Gleich geht es weiter", "next_in": "Nächste Sendung in ",
        "days": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
        "months": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
                   "November", "Dezember"],
    },
    "es": {
        "name": "Español", "today_at": "Hoy a las {hm}", "tomorrow_at": "Mañana a las {hm}",
        "date_at": "{wd} {d} de {mon} a las {hm}", "day_at": "{wd} a las {hm}", "episode": "Temporada {s}, episodio {e}",
        "sep": ": ", "up_next": "A continuación, a las {hm}: {title}", "coming_up_next": "A continuación",
        "later_on": "Más tarde en {channel}", "coming_soon": "Próximamente", "live": "En directo", "new": "Estreno",
        "repeat": "Reposición", "back_soon": "Volvemos enseguida", "next_in": "Siguiente programa en ",
        "days": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                   "noviembre", "diciembre"],
    },
    "it": {
        "name": "Italiano", "today_at": "Oggi alle {hm}", "tomorrow_at": "Domani alle {hm}",
        "date_at": "{wd} {d} {mon} alle {hm}", "day_at": "{wd} alle {hm}", "episode": "Stagione {s}, episodio {e}",
        "sep": ": ", "up_next": "A seguire alle {hm}: {title}", "coming_up_next": "A seguire",
        "later_on": "Più tardi su {channel}", "coming_soon": "Prossimamente", "live": "In diretta", "new": "Prima visione",
        "repeat": "Replica", "back_soon": "Torniamo subito", "next_in": "Prossimo programma tra ",
        "days": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"],
        "months": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
                   "novembre", "dicembre"],
    },
    "pt": {
        "name": "Português", "today_at": "Hoje às {hm}", "tomorrow_at": "Amanhã às {hm}",
        "date_at": "{wd}, {d} de {mon} às {hm}", "day_at": "{wd} às {hm}", "episode": "Temporada {s}, episódio {e}",
        "sep": ": ", "up_next": "A seguir, às {hm}: {title}", "coming_up_next": "A seguir",
        "later_on": "Mais tarde em {channel}", "coming_soon": "Em breve", "live": "Em direto", "new": "Estreia",
        "repeat": "Repetição", "back_soon": "Voltamos já", "next_in": "Próximo programa em ",
        "days": ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"],
        "months": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
                   "novembro", "dezembro"],
    },
    "nl": {
        "name": "Nederlands", "today_at": "Vandaag om {hm}", "tomorrow_at": "Morgen om {hm}",
        "date_at": "{wd} {d} {mon} om {hm}", "day_at": "{wd} om {hm}", "episode": "Seizoen {s}, aflevering {e}",
        "sep": ": ", "up_next": "Hierna om {hm}: {title}", "coming_up_next": "Hierna", "later_on": "Later op {channel}",
        "coming_soon": "Binnenkort", "live": "Live", "new": "Nieuw", "repeat": "Herhaling", "back_soon": "Zo terug",
        "next_in": "Volgend programma over ",
        "days": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"],
        "months": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
                   "november", "december"],
    },
    "sv": {
        "name": "Svenska", "today_at": "I dag kl. {hm}", "tomorrow_at": "I morgon kl. {hm}",
        "date_at": "{wd} {d} {mon} kl. {hm}", "day_at": "{wd} kl. {hm}", "episode": "Säsong {s}, avsnitt {e}", "sep": ": ",
        "up_next": "Härnäst kl. {hm}: {title}", "coming_up_next": "Härnäst", "later_on": "Senare på {channel}",
        "coming_soon": "Kommer snart", "live": "Direkt", "new": "Ny", "repeat": "Repris", "back_soon": "Strax tillbaka",
        "next_in": "Nästa program om ",
        "days": ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"],
        "months": ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
                   "november", "december"],
    },
    "da": {
        "name": "Dansk", "today_at": "I dag kl. {hm}", "tomorrow_at": "I morgen kl. {hm}",
        "date_at": "{wd} {d}. {mon} kl. {hm}", "day_at": "{wd} kl. {hm}", "episode": "Sæson {s}, afsnit {e}", "sep": ": ",
        "up_next": "Næste program kl. {hm}: {title}", "coming_up_next": "Næste program", "later_on": "Senere på {channel}",
        "coming_soon": "Kommer snart", "live": "Direkte", "new": "Ny", "repeat": "Genudsendelse",
        "back_soon": "Vi er tilbage om lidt", "next_in": "Næste program om ",
        "days": ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"],
        "months": ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober",
                   "november", "december"],
    },
    "nb": {
        "name": "Norsk bokmål", "today_at": "I dag kl. {hm}", "tomorrow_at": "I morgen kl. {hm}",
        "date_at": "{wd} {d}. {mon} kl. {hm}", "day_at": "{wd} kl. {hm}", "episode": "Sesong {s}, episode {e}", "sep": ": ",
        "up_next": "Neste program kl. {hm}: {title}", "coming_up_next": "Neste program", "later_on": "Senere på {channel}",
        "coming_soon": "Kommer snart", "live": "Direkte", "new": "Ny", "repeat": "Reprise", "back_soon": "Straks tilbake",
        "next_in": "Neste program om ",
        "days": ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"],
        "months": ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober",
                   "november", "desember"],
    },
}

# How a time is said aloud (0.7.0, audio description on promos): a speech program reads "21:00" as digits, so the hour
# and the minutes are given as numbers with the language's own word. "say" replaces what is written short.
SPOKEN = {
    "en": {"hour": "{h} o'clock", "hour_min": "{h} {m}", "small": "{h} oh {m}"},
    "fr": {"hour": "{h} heures", "hour_min": "{h} heures {m}"},
    "de": {"hour": "{h} Uhr", "hour_min": "{h} Uhr {m}"},
    "es": {"hour": "{h} horas", "hour_min": "{h} horas {m}"},
    "it": {"hour": "{h}", "hour_min": "{h} e {m}"},
    "pt": {"hour": "{h} horas", "hour_min": "{h} horas e {m}"},
    "nl": {"hour": "{h} uur", "hour_min": "{h} uur {m}"},
    "sv": {"hour": "{h}", "hour_min": "{h} och {m}", "say": {"kl.": "klockan"}},
    "da": {"hour": "{h}", "hour_min": "{h} {m}", "say": {"kl.": "klokken"}},
    "nb": {"hour": "{h}", "hour_min": "{h} {m}", "say": {"kl.": "klokken"}},
}

# Jellyfin gives a sound track's language as ISO 639-2, bibliographic (fre, ger, dut) or terminology (fra, deu, nld),
# and some files carry the two-letter code. Norwegian may be nor, nob or nno.
SOUND_CODES = {
    "en": {"eng", "en"}, "fr": {"fre", "fra", "fr"}, "de": {"ger", "deu", "de"}, "es": {"spa", "es"},
    "it": {"ita", "it"}, "pt": {"por", "pt"}, "nl": {"dut", "nld", "nl"}, "sv": {"swe", "sv"}, "da": {"dan", "da"},
    "nb": {"nor", "nob", "nno", "no", "nb", "nn"},
}

# The language and country Jellyfin passes to its metadata providers (TMDB) for titles and descriptions.
METADATA = {"fr": ("fr", "FR"), "de": ("de", "DE"), "es": ("es", "ES"), "it": ("it", "IT"), "pt": ("pt", "PT"),
            "nl": ("nl", "NL"), "sv": ("sv", "SE"), "da": ("da", "DK"), "nb": ("no", "NO")}


def code(lang):
    """The language code to use: the setting when it is one offered, else English."""
    lang = str(lang or "").strip().lower()
    return lang if lang in TABLES else DEFAULT


def table(lang):
    return TABLES[code(lang)]


def _first_up(words):
    return words[:1].upper() + words[1:]


def hm(t):
    return time.strftime("%H:%M", time.localtime(t))


def when(t, now=None, lang=DEFAULT):
    """The date and time a programme is shown: "Today at 18:30", "Tomorrow at 06:00", "Saturday 22 November at 21:00";
    "Morgen um 06:00" in German."""
    w = table(lang)
    now = time.time() if now is None else now
    lt, ln = time.localtime(t), time.localtime(now)
    day = (time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) - time.mktime((ln.tm_year, ln.tm_mon, ln.tm_mday, 0, 0, 0, 0, 0, -1))) / 86400
    at = time.strftime("%H:%M", lt)
    if round(day) == 0:
        return w["today_at"].format(hm=at)
    if round(day) == 1:
        return w["tomorrow_at"].format(hm=at)
    return _first_up(w["date_at"].format(wd=w["days"][lt.tm_wday], d=lt.tm_mday, mon=w["months"][lt.tm_mon - 1], hm=at))


def day_time(t, lang=DEFAULT):
    """The day and time that stay true all week: "Sunday at 21:00". For promos, made days before they play."""
    w = table(lang)
    lt = time.localtime(t)
    return _first_up(w["day_at"].format(wd=w["days"][lt.tm_wday], hm=time.strftime("%H:%M", lt)))


def time_spoken(t, lang=DEFAULT):
    """A time as a speech program should be given it: "21 o'clock", "21 30", "21 heures 30", "21 Uhr"."""
    sp = SPOKEN[code(lang)]
    lt = time.localtime(t)
    if lt.tm_min == 0:
        return sp["hour"].format(h=lt.tm_hour)
    return (sp.get("small") if lt.tm_min < 10 and sp.get("small") else sp["hour_min"]).format(h=lt.tm_hour, m=lt.tm_min)


def day_time_spoken(t, lang=DEFAULT):
    """day_time for a voice (0.7.0): "Sunday at 21 o'clock", "Sonntag um 21 Uhr", "söndag klockan 21"."""
    w, sp = table(lang), SPOKEN[code(lang)]
    said = w["day_at"].format(wd=w["days"][time.localtime(t).tm_wday], hm=time_spoken(t, lang))
    for short, full in (sp.get("say") or {}).items():
        said = said.replace(short, full)
    return _first_up(said)


def episode(s, e, lang=DEFAULT):
    return table(lang)["episode"].format(s=s, e=e)


def sep(lang=DEFAULT):
    """What goes between a title and its episode: ": ", or " : " in French."""
    return table(lang)["sep"]


def up_next(t, title, lang=DEFAULT):
    return table(lang)["up_next"].format(hm=hm(t), title=title)


def heading(card, channel, lang=DEFAULT):
    """A card's heading: Coming up next for the next programme, Later on and the channel's name for one after it."""
    w = table(lang)
    return w["coming_up_next"] if card == "next" else w["later_on"].format(channel=channel)


def word(key, lang=DEFAULT):
    """One of the single words or phrases: live, new, repeat, coming_soon, back_soon, next_in."""
    return table(lang)[key]


def sound_codes(lang):
    return SOUND_CODES.get(code(lang), set())
