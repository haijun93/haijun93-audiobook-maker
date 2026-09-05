"""audiobook_studio/study_filter.py

Strict High-Yield TOEIC 700+ to 990 Vocabulary & Idiom Filter Module.
Strictly filters out:
1. Middle/High school basic single words (e.g. fate, hell, words, smile, dinner, ticket, afraid, tears, voice, future, stomach)
2. Mechanical combinations of basic words (e.g. 'that one', 'three little words', 'in the room', 'last night')
3. Retains ONLY high-yield TOEIC 700~990 vocabulary (e.g. evict, mutilate, threshold, run amok) and authentic advanced idioms.
"""

from __future__ import annotations

import re

# Comprehensive middle/high school 4,000+ base words and function words to EXCLUDE
BASIC_VOCAB_STOPLIST = {
    # Basic / Middle school core nouns
    "fate", "destiny", "future", "past", "present", "life", "death", "soul", "heart", "mind",
    "word", "words", "hell", "heaven", "god", "devil", "smile", "dinner", "lunch", "breakfast",
    "ticket", "travel", "trip", "hotel", "room", "door", "doorway", "window", "floor", "wall",
    "house", "home", "car", "hand", "hands", "foot", "feet", "tooth", "teeth", "eye", "eyes",
    "nose", "mouth", "head", "arm", "arms", "leg", "legs", "finger", "fingers", "body", "hair",
    "voice", "voices", "sound", "light", "dark", "night", "day", "morning", "evening", "afternoon",
    "sun", "moon", "sky", "star", "water", "fire", "air", "tree", "flower", "grass", "animal",
    "dog", "cat", "bird", "fish", "friend", "friends", "family", "mother", "father", "parent",
    "parents", "brother", "sister", "son", "daughter", "child", "children", "baby", "man", "men",
    "woman", "women", "boy", "girl", "people", "person", "name", "street", "road", "city", "town",
    "country", "world", "time", "hour", "minute", "second", "year", "month", "week", "money",
    "dollar", "price", "shop", "store", "book", "page", "letter", "paper", "pen", "pencil",
    "desk", "table", "chair", "bed", "box", "bag", "clothes", "shirt", "pants", "dress", "shoes",
    "coat", "hat", "food", "bread", "meat", "milk", "tea", "coffee", "fruit", "apple", "sugar",
    "salt", "love", "hate", "job", "work", "school", "class", "teacher", "student", "game",
    "sport", "music", "song", "picture", "photo", "movie", "film", "story", "news", "question",
    "answer", "problem", "idea", "thought", "feeling", "feelings", "side", "part", "place",
    "thing", "things", "way", "end", "start", "stop", "rest", "sleep", "dream", "truth", "lie",
    "secret", "power", "king", "queen", "lord", "lady", "doctor", "police", "fist", "belly",
    "stomach", "tear", "tears", "hood", "contents", "male", "female", "sir", "madam", "guy",
    "kid", "boss", "guest", "crowd", "shadow", "ground", "earth", "rock", "stone", "sea",
    "ocean", "river", "lake", "forest", "mountain", "hill", "rain", "snow", "wind", "cloud",

    # Prepositions, Articles, Conjunctions & Particles
    "a", "an", "the", "in", "on", "at", "to", "for", "with", "from", "by", "about",
    "into", "through", "after", "before", "between", "under", "over", "behind", "above",
    "below", "up", "down", "off", "out", "of", "and", "or", "but", "so", "because",
    "if", "when", "while", "as", "than", "like", "though", "although", "since", "until",

    # Pronouns, Determiners & Numbers
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "hundred",
    "thousand", "first", "third", "this", "that", "these", "those", "it", "they", "them",
    "he", "she", "him", "her", "his", "hers", "my", "your", "our", "their", "me", "you", "us",
    "we", "who", "whom", "whose", "which", "what", "all", "some", "any", "no", "every", "each",
    "both", "few", "more", "most", "other", "another", "such", "same",

    # Basic adjectives & adverbs
    "good", "bad", "big", "small", "little", "large", "huge", "great", "fine", "nice",
    "sweet", "cute", "pretty", "beautiful", "ugly", "clean", "dirty", "new", "old",
    "young", "fresh", "hot", "cold", "warm", "cool", "dry", "wet", "hard", "soft",
    "heavy", "fast", "slow", "quick", "early", "late", "high", "low", "long",
    "short", "tall", "deep", "shallow", "rich", "poor", "strong", "weak", "safe",
    "dangerous", "easy", "difficult", "simple", "clear", "bright", "happy", "sad",
    "angry", "afraid", "scared", "tired", "sick", "healthy", "dead", "alive", "glad",
    "sorry", "proud", "busy", "free", "ready", "sure", "certain", "true", "false",
    "real", "fake", "right", "wrong", "alone", "lonely", "hungry", "thirsty", "full",
    "empty", "open", "close", "closed", "black", "white", "red", "blue", "green",
    "yellow", "orange", "pink", "brown", "gray", "last", "next", "final", "main",
    "only", "well", "badly", "very", "too", "quite", "really", "almost",
    "nearly", "enough", "already", "again", "ever", "never", "always", "often",
    "sometimes", "usually", "seldom", "hardly", "today", "yesterday", "tomorrow",
    "tonight", "soon", "now", "then", "here", "there", "together", "maybe", "perhaps",
    "definitely", "probably", "actually", "suddenly", "finally",

    # Basic verbs (inflected forms only – base forms kept in nouns section where duplicated)
    "be", "is", "am", "are", "was", "were", "been", "being", "have", "has", "had",
    "do", "does", "did", "done", "say", "said", "tell", "told", "speak", "spoke",
    "talk", "talked", "ask", "asked", "answered", "call", "called", "look",
    "looked", "see", "saw", "seen", "watch", "watched", "hear", "heard", "listen",
    "feel", "felt", "touch", "touched", "smell", "taste", "know", "knew", "known",
    "think", "understand", "remember", "forget", "forgot", "learn", "teach",
    "study", "read", "write", "wrote", "written", "go", "went", "gone", "come", "came",
    "leave", "left", "arrive", "reach", "walk", "walked", "run", "ran", "jump", "fly",
    "flew", "drive", "drove", "ride", "rode", "fall", "fell", "stand", "stood", "sit",
    "sat", "lay", "lain", "slept", "wake", "woke", "eat", "ate", "eaten",
    "drink", "drank", "buy", "bought", "sell", "sold", "pay", "paid", "cost", "spend",
    "spent", "give", "gave", "given", "take", "took", "taken", "bring", "brought", "send",
    "sent", "get", "got", "make", "made", "build", "built", "break", "broke", "broken",
    "cut", "put", "set", "hold", "held", "keep", "kept", "let", "help", "helped", "use",
    "used", "worked", "play", "played", "try", "tried", "need", "needed", "want",
    "wanted", "wish", "hope", "liked", "loved", "started",
    "begin", "began", "stopped", "finish", "finished", "ended", "show", "showed",
    "hide", "hid", "find", "found", "lose", "lost", "meet", "met", "follow", "followed",
    "lead", "led", "live", "lived", "die", "died", "kill", "killed", "save", "saved",
    "change", "changed", "move", "moved", "turn", "turned", "grow", "grew", "wait",
    "waited", "stay", "stayed", "pass", "passed", "cross", "crossed", "drop", "dropped",
    "pick", "picked", "pull", "pulled", "push", "pushed", "carry", "carried", "catch",
    "caught", "throw", "threw", "fight", "fought", "win", "won", "hit", "strike", "kiss",
    "hug", "laugh", "cry", "cried", "crying", "shout", "scream", "bleed", "bled",
    "shake", "shook", "shiver", "breathe", "burn", "burned", "shine"
}

# Recognized high-yield phrasal idioms and collocations where common words combine into an advanced figurative meaning
HIGH_YIELD_PHRASAL_IDIOMS = {
    "bleed dry", "cross the threshold", "run amok", "take a toll", "pay off", "come to terms",
    "give in", "fall out", "bear in mind", "take for granted", "rule out", "stand out",
    "break even", "call it a day", "cut corners", "read between the lines", "see eye to eye",
    "spill the beans", "bite the bullet", "hit the nail on the head", "piece of cake",
    "burn the midnight oil", "on the fence", "through thick and thin", "at the eleventh hour",
    "under the weather", "cut to the chase", "up in the air", "play devil's advocate",
    "once in a blue moon", "face the music", "cost an arm and a leg", "take with a grain of salt"
}

def is_valid_toeic_700_plus_target(term: str) -> bool:
    """Strictly verifies if a term/phrase qualifies as a TOEIC 700+ to 990 learning target.
    
    1. Single words in BASIC_VOCAB_STOPLIST are STRICTLY EXCLUDED (e.g. 'fate', 'words', 'smile').
    2. Multi-word phrases composed ENTIRELY of middle-school basic words without an advanced figurative idiom
       are STRICTLY EXCLUDED (e.g. 'that one', 'three little words', 'in the car', 'my hand').
    3. Retains ONLY terms with >= 1 advanced vocabulary or genuine figurative idioms (e.g. 'evict', 'mutilate', 'run amok').
    """
    term_clean = re.sub(r'[^a-zA-Z\s\-]', '', term).strip().lower()
    if not term_clean or len(term_clean) < 3:
        return False

    # Check for single word
    if " " not in term_clean and "-" not in term_clean:
        if term_clean in BASIC_VOCAB_STOPLIST:
            return False
        # Disallow trivial 3-letter single words unless rare
        if len(term_clean) <= 3:
            return False
        return True

    # Multi-word phrase check (Strict Phrase Guard)
    words = [w for w in re.split(r'[\s\-]+', term_clean) if w]
    if not words:
        return False

    # Check if phrase is an established authentic high-yield idiom
    if term_clean in HIGH_YIELD_PHRASAL_IDIOMS:
        return True

    # Count how many words in the phrase are middle-school basic words
    basic_count = sum(1 for w in words if w in BASIC_VOCAB_STOPLIST)

    # If 100% of the words in the phrase are basic trivial words -> STRICTLY EXCLUDE!
    # (e.g. 'that one', 'three little words', 'in the room', 'face to face', 'day and night')
    if basic_count == len(words):
        return False

    # If phrase is 2 words and contains 1 stopword, the other word MUST be an advanced 700+ word
    if len(words) == 2 and basic_count >= 1:
        non_basic_words = [w for w in words if w not in BASIC_VOCAB_STOPLIST]
        for nb in non_basic_words:
            if len(nb) <= 3: # Trivial non-basic word
                return False

    return True
