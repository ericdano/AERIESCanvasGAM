import random
import string
import re

# ---------------- CONFIG ----------------
TOTAL_PASSWORDS = 6000
DIGITS_AT_END = 3

VOWELS = "aeiou"
CONSONANTS = "bcdfghjkmnprstvwxz" # removed ambiguous / harsh sounds
SYMBOL_SUBS = {
'a': '@',
's': '$',
'i': '!',
'l': '!',
'e': '&'
}
SYMBOLS = list(set(SYMBOL_SUBS.values()))

# Very conservative blacklist (can be expanded)
OFFENSIVE_SUBSTRINGS = {
    # General profanity
    "fuck", "shit", "damn", "hell", "piss", "crap", "bitch", "bastard",
    
    # Anatomical/Sexual terms
    "sex", "porn", "anal", "ass", "butt", "tit", "boob", "penis", "dick", 
    "vagina", "cunt", "clit", "balls", "nuts", "jizz", "shaft", "hardon",
    
    # Slurs and Hate Speech (Crucial for school environments)
    "fag", "gay", "homo", "nigger", "spic", "chink", "kike", "retard",
    
    # Common insults/Mean-spirited words
    "dumb", "stupid", "idiot", "fat", "ugly", "obese", "loser", "hate",
    "kill", "die", "slave", "nazi", "hitler","obese",
    "nigger", "nigga", "fag", "faggot", "kike", "spic", "chink", "cunt", 
    "retard", "tranny", "dyke", "nazi", "hitler", "negro",

    # --- Tier 2: Sexual & Anatomical Slang ---
    "fuck", "shit", "bitch", "whore", "slut", "porn", "anal", "vagina", 
    "penis", "dick", "cock", "tits", "boob", "clit", "jizz", "cum", 
    "boner", "balls", "nuts", "bastard", "twat", "wanker", "prick",

    # --- Tier 3: Modern Internet Slang & Evasion Terms ---
    "seggs", "unalive", "kys", "stfu", "pwned", "haxor", "n00b", "leets",

    # --- Tier 4: School-Specific Mean-Spirited Words ---
    "ugly", "fat", "obese", "stupid", "idiot", "dumb", "loser", "hate", 
    "kill", "die", "slave", "freak", "weirdo", "scum", "trash"
    }

# ----------------------------------------

def is_safe(word):
    lowered = word.lower()
    return not any(bad in lowered for bad in OFFENSIVE_SUBSTRINGS)

def make_pronounceable_base():
    # Alternating consonant/vowel pattern: CVCVC
    base = ""
    for i in range(5):
        if i % 2 == 0:
            base += random.choice(CONSONANTS)
        else:
            base += random.choice(VOWELS)
    return base

def apply_symbol_substitution(word):
    candidates = [i for i, c in enumerate(word) if c in SYMBOL_SUBS]
    if not candidates:
        return None
    idx = random.choice(candidates)
    return word[:idx] + SYMBOL_SUBS[word[idx]] + word[idx+1:]

def generate_password():
    while True:
        base = make_pronounceable_base()

        if not is_safe(base):
            continue

        with_symbol = apply_symbol_substitution(base)
        if not with_symbol:
            continue
            
        # FIXED: These lines are now properly indented inside the loop
        capital = random.choice(string.ascii_uppercase)
        digits = ''.join(random.choices(string.digits, k=DIGITS_AT_END))

        password = capital + with_symbol + digits
        return password # Return immediately once a valid password is built

def generate_unique_passwords(n):
    passwords = set()
    attempts = 0
    max_attempts = n * 100 # Safety to prevent infinite loop
    
    while len(passwords) < n and attempts < max_attempts:
        passwords.add(generate_password())
        attempts += 1
    return sorted(passwords)

# --------- RUN + EXPORT ----------
passwords = generate_unique_passwords(TOTAL_PASSWORDS)

with open("student_passwords.csv", "w") as f:
    for p in passwords:
        f.write(p + "\n")

print(f"Generated {len(passwords)} passwords.")