"""audiobook_studio/study_filter.py

High-Yield TOEIC 700+ to 990 Vocabulary & Idiom Filter Module.
Filters out middle school basic vocabulary (e.g. hell, words, smile, dinner, ticket, afraid)
and retains ONLY high-yield TOEIC 700~990 vocabulary, advanced literary expressions, and collocations.
"""

from __future__ import annotations

import re

# Comprehensive middle school & elementary 3,500 base words to EXCLUDE from single-word Word Wise hints
BASIC_VOCAB_STOPLIST = {
    # Basic nouns
    "word", "words", "hell", "smile", "dinner", "lunch", "breakfast", "ticket", "travel",
    "trip", "hotel", "room", "door", "window", "floor", "wall", "house", "home", "car",
    "hand", "hands", "foot", "feet", "tooth", "teeth", "eye", "eyes", "nose", "mouth",
    "head", "arm", "arms", "leg", "legs", "finger", "fingers", "body", "hair", "voice",
    "sound", "light", "night", "day", "morning", "evening", "afternoon", "sun", "moon",
    "sky", "star", "water", "fire", "air", "tree", "flower", "grass", "animal", "dog",
    "cat", "bird", "fish", "friend", "family", "mother", "father", "parent", "parents",
    "brother", "sister", "son", "daughter", "child", "children", "baby", "man", "men",
    "woman", "women", "boy", "girl", "people", "person", "name", "street", "road", "city",
    "town", "country", "world", "time", "hour", "minute", "second", "year", "month", "week",
    "money", "dollar", "price", "shop", "store", "book", "page", "letter", "paper", "pen",
    "pencil", "desk", "table", "chair", "bed", "box", "bag", "clothes", "shirt", "pants",
    "dress", "shoes", "coat", "hat", "food", "bread", "meat", "milk", "tea", "coffee",
    "fruit", "apple", "sugar", "salt", "love", "hate", "life", "death", "job", "work",
    "school", "class", "teacher", "student", "game", "sport", "music", "song", "picture",
    "photo", "movie", "film", "story", "news", "question", "answer", "problem", "idea",
    "thought", "feeling", "mind", "heart", "side", "part", "place", "thing", "things",
    "way", "road", "end", "start", "stop", "rest", "sleep", "dream", "truth", "lie",
    "secret", "power", "king", "queen", "lord", "lady", "god", "doctor", "police",
    
    # Basic adjectives & adverbs
    "good", "bad", "big", "small", "little", "large", "huge", "great", "fine", "nice",
    "sweet", "cute", "pretty", "beautiful", "ugly", "clean", "dirty", "new", "old",
    "young", "fresh", "hot", "cold", "warm", "cool", "dry", "wet", "hard", "soft",
    "heavy", "light", "fast", "slow", "quick", "early", "late", "high", "low", "long",
    "short", "tall", "deep", "shallow", "rich", "poor", "strong", "weak", "safe",
    "dangerous", "easy", "difficult", "simple", "hard", "clear", "dark", "bright",
    "happy", "sad", "angry", "afraid", "scared", "tired", "sick", "healthy", "dead",
    "alive", "glad", "sorry", "proud", "busy", "free", "ready", "sure", "certain",
    "true", "false", "real", "fake", "right", "wrong", "same", "different", "alone",
    "lonely", "hungry", "thirsty", "full", "empty", "open", "close", "closed",
    "black", "white", "red", "blue", "green", "yellow", "orange", "pink", "brown", "gray",
    "first", "second", "third", "last", "next", "final", "main", "only", "well", "badly",
    "very", "too", "so", "quite", "really", "almost", "nearly", "enough", "already",
    "again", "ever", "never", "always", "often", "sometimes", "usually", "seldom",
    "hardly", "today", "yesterday", "tomorrow", "tonight", "soon", "now", "then",
    "here", "there", "everywhere", "nowhere", "somewhere", "anywhere", "together",
    
    # Basic verbs
    "be", "is", "am", "are", "was", "were", "been", "being", "have", "has", "had",
    "do", "does", "did", "done", "say", "said", "tell", "told", "speak", "spoke",
    "talk", "talked", "ask", "asked", "answer", "call", "called", "look", "looked",
    "see", "saw", "seen", "watch", "hear", "heard", "listen", "feel", "felt", "touch",
    "smell", "taste", "know", "knew", "known", "think", "thought", "understand",
    "remember", "forget", "forgot", "learn", "teach", "study", "read", "write", "wrote",
    "listen", "go", "went", "gone", "come", "came", "leave", "left", "arrive", "reach",
    "walk", "run", "ran", "jump", "fly", "flew", "drive", "drove", "ride", "rode",
    "fall", "fell", "stand", "stood", "sit", "sat", "lie", "lay", "lain", "sleep",
    "slept", "wake", "woke", "eat", "ate", "eaten", "drink", "drank", "buy", "bought",
    "sell", "sold", "pay", "paid", "cost", "spend", "spent", "give", "gave", "given",
    "take", "took", "taken", "bring", "brought", "send", "sent", "get", "got", "make",
    "made", "build", "built", "break", "broke", "broken", "cut", "put", "set", "hold",
    "held", "keep", "kept", "let", "help", "helped", "use", "used", "work", "worked",
    "play", "played", "try", "tried", "need", "needed", "want", "wanted", "wish",
    "hope", "hoped", "like", "liked", "love", "loved", "hate", "start", "started",
    "begin", "began", "stop", "stopped", "finish", "finished", "end", "open", "close",
    "show", "showed", "hide", "hid", "find", "found", "lose", "lost", "meet", "met",
    "follow", "followed", "lead", "led", "live", "lived", "die", "died", "kill", "killed",
    "save", "saved", "change", "changed", "move", "moved", "turn", "turned", "grow",
    "grew", "wait", "waited", "stay", "stayed", "pass", "passed", "cross", "crossed",
    "drop", "dropped", "pick", "picked", "pull", "pulled", "push", "pushed", "carry",
    "carried", "bring", "brought", "catch", "caught", "throw", "threw", "fight", "fought",
    "win", "won", "lose", "lost", "hit", "strike", "struck", "kiss", "kissed", "hug",
    "smile", "smiled", "laugh", "laughed", "cry", "cried", "shout", "shouted", "scream",
    "bleed", "bled", "shake", "shook", "shiver", "breathe", "burn", "burned", "shine"
}

def is_valid_toeic_700_plus_target(term: str) -> bool:
    """Returns True if the term is suitable for TOEIC 700+ to 990 learners.
    
    1. Multi-word phrases, idioms, collocations (e.g. 'bleed dry', 'cross the threshold')
       are ALWAYS VALID and high-yield.
    2. Single words in the BASIC_VOCAB_STOPLIST are EXCLUDED to prevent visual clutter
       and middle-school level trivia.
    3. Words shorter than 4 letters are generally excluded unless part of a collocation.
    """
    term_clean = term.strip().lower()
    
    # 1. Multi-word phrases / idioms are high value (Collocations, Phrasal Verbs)
    if " " in term_clean or "-" in term_clean:
        return True
        
    # 2. Check basic stoplist for single words
    if term_clean in BASIC_VOCAB_STOPLIST:
        return False
        
    # 3. Lemmatized basic checks (e.g. smiled -> smile, words -> word)
    if term_clean.endswith("s") and term_clean[:-1] in BASIC_VOCAB_STOPLIST:
        return False
    if term_clean.endswith("es") and term_clean[:-2] in BASIC_VOCAB_STOPLIST:
        return False
    if term_clean.endswith("ed") and term_clean[:-2] in BASIC_VOCAB_STOPLIST:
        return False
    if term_clean.endswith("ed") and term_clean[:-1] in BASIC_VOCAB_STOPLIST:
        return False
    if term_clean.endswith("ing") and term_clean[:-3] in BASIC_VOCAB_STOPLIST:
        return False
    if term_clean.endswith("ing") and term_clean[:-4] in BASIC_VOCAB_STOPLIST:
        return False
    if term_clean.endswith("ly") and term_clean[:-2] in BASIC_VOCAB_STOPLIST:
        # e.g. gladly, nicely -> exclude
        return False
        
    # 4. Length check
    if len(term_clean) < 4:
        return False
        
    return True
