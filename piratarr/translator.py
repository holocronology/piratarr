"""Pirate speak translation engine.

Translates standard English text into pirate speak using dictionary-based
word/phrase substitution with regex for whole-word matching.
"""

import re
import random

# Phrase substitutions (checked first, order matters)
PHRASE_MAP = [
    (r"\bmy friend\b", "me hearty"),
    (r"\bmy friends\b", "me hearties"),
    (r"\blook at that\b", "shiver me timbers"),
    (r"\boh my god\b", "blow me down"),
    (r"\byou all\b", "ye scallywags"),
    (r"\bcome here\b", "come 'ere"),
    (r"\bover there\b", "o'er yonder"),
    (r"\bright now\b", "right this instant, savvy"),
    (r"\bI don't know\b", "I be not knowin'"),
    (r"\bI don't\b", "I don't be"),
    (r"\bdon't you\b", "don't ye"),
    (r"\bwhat do you\b", "what d'ye"),
    (r"\bdo you\b", "d'ye"),
    (r"\bwhat are you\b", "what be ye"),
    (r"\bwhere are you\b", "where be ye"),
    (r"\bwho are you\b", "who be ye"),
    (r"\bare you\b", "be ye"),
    (r"\bof course\b", "aye, o' course"),
    (r"\bI am\b", "I be"),
    (r"\byou are\b", "ye be"),
    (r"\bthey are\b", "they be"),
    (r"\bwe are\b", "we be"),
    (r"\bit is\b", "it be"),
    (r"\bthere is\b", "there be"),
    (r"\bthere are\b", "there be"),
    (r"\bhe is\b", "he be"),
    (r"\bshe is\b", "she be"),
]

# Single-word substitutions
WORD_MAP = {
    "hello": "ahoy",
    "hi": "ahoy",
    "hey": "ahoy",
    "greetings": "ahoy",
    "friend": "matey",
    "friends": "hearties",
    "buddy": "matey",
    "pal": "matey",
    "man": "landlubber",
    "dude": "bucko",
    "sir": "cap'n",
    "madam": "lass",
    "ma'am": "lass",
    "boy": "lad",
    "girl": "lass",
    "woman": "lass",
    "women": "lasses",
    "men": "scallywags",
    "children": "little scallywags",
    "child": "wee scallywag",
    "kid": "wee scallywag",
    "kids": "little scallywags",
    "people": "scallywags",
    "person": "soul",
    "stranger": "landlubber",
    "everyone": "all hands",
    "everybody": "all hands",
    "someone": "some scurvy dog",
    "anyone": "any scurvy dog",
    "nobody": "no scurvy dog",
    "yes": "aye",
    "yeah": "aye",
    "yep": "aye",
    "no": "nay",
    "nope": "nay",
    "never": "ne'er",
    "ever": "e'er",
    "forever": "fore'er",
    "okay": "aye aye",
    "ok": "aye aye",
    "sure": "aye",
    "money": "doubloons",
    "cash": "doubloons",
    "gold": "booty",
    "treasure": "booty",
    "reward": "plunder",
    "dollar": "doubloon",
    "dollars": "doubloons",
    "coin": "piece o' eight",
    "coins": "pieces o' eight",
    "drink": "grog",
    "drinks": "grog",
    "beer": "grog",
    "wine": "grog",
    "alcohol": "rum",
    "liquor": "rum",
    "whiskey": "rum",
    "water": "the briny deep",
    "ocean": "the seven seas",
    "sea": "the briny deep",
    "boat": "ship",
    "car": "ship",
    "vehicle": "vessel",
    "house": "quarters",
    "home": "port",
    "room": "cabin",
    "bed": "hammock",
    "jail": "the brig",
    "prison": "the brig",
    "bathroom": "the head",
    "floor": "deck",
    "door": "hatch",
    "window": "porthole",
    "stairs": "gangway",
    "kitchen": "the galley",
    "food": "grub",
    "meal": "grub",
    "dinner": "grub",
    "lunch": "grub",
    "breakfast": "mornin' grub",
    "eat": "feast upon",
    "eating": "feastin' upon",
    "flag": "Jolly Roger",
    "map": "chart",
    "boss": "captain",
    "leader": "captain",
    "manager": "captain",
    "teacher": "captain",
    "enemy": "scurvy dog",
    "enemies": "scurvy dogs",
    "fight": "battle",
    "fighting": "battlin'",
    "gun": "cannon",
    "guns": "cannons",
    "weapon": "cutlass",
    "weapons": "cutlasses",
    "knife": "dagger",
    "sword": "cutlass",
    "kill": "send to Davy Jones",
    "die": "meet Davy Jones",
    "died": "met Davy Jones",
    "dead": "in Davy Jones' locker",
    "death": "Davy Jones' locker",
    "steal": "plunder",
    "stole": "plundered",
    "stolen": "plundered",
    "stealing": "plunderin'",
    "rob": "pillage",
    "robbing": "pillagin'",
    "robbery": "pillagin'",
    "thief": "pirate",
    "criminal": "buccaneer",
    "look": "feast yer eyes",
    "looking": "lookin'",
    "see": "spy",
    "saw": "spied",
    "seeing": "spyin'",
    "watching": "keepin' a weather eye on",
    "run": "make haste",
    "running": "makin' haste",
    "walk": "swagger",
    "walking": "swaggerin'",
    "go": "set sail",
    "going": "settin' sail",
    "leave": "shove off",
    "leaving": "shovin' off",
    "left": "shoved off",
    "come": "sail 'ere",
    "coming": "sailin' 'ere",
    "stop": "avast",
    "wait": "hold fast",
    "hurry": "look lively",
    "think": "reckon",
    "thinking": "reckonin'",
    "thought": "reckoned",
    "know": "be knowin'",
    "understand": "savvy",
    "right": "starboard",
    "left": "port",
    "happy": "jolly",
    "sad": "glum",
    "angry": "ornery",
    "scared": "lily-livered",
    "brave": "bold as brass",
    "stupid": "addled",
    "smart": "sharp as a tack",
    "crazy": "touched in the head",
    "drunk": "three sheets to the wind",
    "tired": "weary",
    "old": "barnacled",
    "young": "green",
    "big": "mighty",
    "small": "wee",
    "little": "wee",
    "beautiful": "fair",
    "ugly": "foul",
    "good": "fine",
    "bad": "foul",
    "great": "grand",
    "terrible": "cursed",
    "wonderful": "grand",
    "amazing": "blimey",
    "awesome": "grand",
    "cool": "shipshape",
    "nice": "fair",
    "sorry": "beggin' yer pardon",
    "please": "if it please ye",
    "thanks": "much obliged",
    "thank": "be thankin'",
    "help": "lend a hand",
    "my": "me",
    "your": "yer",
    "yours": "yers",
    "you": "ye",
    "is": "be",
    "are": "be",
    "am": "be",
    "was": "were",
    "the": "th'",
    "to": "t'",
    "for": "fer",
    "of": "o'",
    "with": "wit'",
    "over": "o'er",
    "ing": "in'",
}

# Pirate exclamations to randomly insert at sentence boundaries
EXCLAMATIONS = [
    "Arrr!",
    "Yarr!",
    "Shiver me timbers!",
    "Blimey!",
    "Avast!",
    "Yo ho ho!",
    "By Blackbeard's ghost!",
    "Savvy?",
]

# Probability of inserting an exclamation after a sentence
EXCLAMATION_CHANCE = 0.12


def _apply_phrase_subs(text: str) -> str:
    """Apply multi-word phrase substitutions."""
    for pattern, replacement in PHRASE_MAP:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _apply_word_subs(text: str) -> str:
    """Apply single-word substitutions with whole-word matching."""

    def replace_word(match):
        word = match.group(0)
        lower = word.lower()
        if lower in WORD_MAP:
            replacement = WORD_MAP[lower]
            # Preserve original capitalization
            if word.isupper():
                return replacement.upper()
            elif word[0].isupper():
                return replacement[0].upper() + replacement[1:]
            return replacement
        return word

    return re.sub(r"\b[a-zA-Z']+\b", replace_word, text)


def _maybe_add_exclamation(text: str) -> str:
    """Randomly insert pirate exclamations after sentence-ending punctuation."""
    if not text.strip():
        return text

    sentences = re.split(r"([.!?]+)", text)
    result = []
    for i, part in enumerate(sentences):
        result.append(part)
        if re.match(r"[.!?]+$", part) and random.random() < EXCLAMATION_CHANCE:
            result.append(" " + random.choice(EXCLAMATIONS))

    return "".join(result)


def _drop_g(text: str) -> str:
    """Drop trailing 'g' from -ing words (runnin', sailin', etc).

    Only applies to words not already in the word map to avoid double-transform.
    """

    def dropper(match):
        word = match.group(0)
        if word.lower() in WORD_MAP:
            return word
        return word[:-1] + "'"

    return re.sub(r"\b\w+ing\b", dropper, text)


def translate(text: str, seed: int | None = None) -> str:
    """Translate English text into pirate speak.

    Args:
        text: The English text to translate.
        seed: Optional random seed for reproducible exclamation placement.

    Returns:
        The pirate-speak translation of the input text.
    """
    if seed is not None:
        random.seed(seed)

    result = _apply_phrase_subs(text)
    result = _apply_word_subs(result)
    result = _drop_g(result)
    result = _maybe_add_exclamation(result)

    return result
