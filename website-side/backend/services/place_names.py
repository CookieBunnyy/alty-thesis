"""Place-name recognition with spaCy's English model (en_core_web_sm).

The regex rules in keywords.py need a cue word ("I work at ...", "near ...").
spaCy's named-entity recognizer finds place names without one, e.g.
"condo Ayala Alabang" or "I work at the Accenture office in Makati".

Startup is not slowed down: the model is imported and loaded in a background
thread (only the tokenizer + NER pipes, ~0.3 s instead of ~2 s), and until it
is ready, or if it is not installed, place_entities() returns [] so the chat
falls back to the regex rules.
"""

import logging
import threading

log = logging.getLogger(__name__)

MODEL = "en_core_web_sm"
# Pipes the recognizer does not need; skipping them cuts load time and memory.
_UNUSED_PIPES = ["parser", "tagger", "lemmatizer", "attribute_ruler", "senter"]
# Countries/cities, other locations, buildings/landmarks, and organisations
# (BGC, company offices). PERSON is ignored: names belong to people.
PLACE_LABELS = {"GPE", "LOC", "FAC", "ORG"}

_nlp = None
_lock = threading.Lock()
_started = False


def _load() -> None:
    global _nlp
    try:
        import spacy

        _nlp = spacy.load(MODEL, exclude=_UNUSED_PIPES)
        log.info("spaCy %s ready (%s)", MODEL, ", ".join(_nlp.pipe_names))
    except Exception as exc:  # model missing or broken: keep the regex rules
        log.warning("spaCy %s unavailable, using regex rules only: %s", MODEL, exc)


def warm_up() -> None:
    """Start loading the model in the background (once)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_load, name="spacy-load", daemon=True).start()


def is_ready() -> bool:
    return _nlp is not None


def place_entities(text: str) -> list[dict]:
    """[{"text", "label", "start", "end"}] for place-like entities in text."""
    if _nlp is None:
        return []
    return [
        {"text": ent.text.strip(), "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
        for ent in _nlp(text).ents
        if ent.label_ in PLACE_LABELS and ent.text.strip()
    ]
