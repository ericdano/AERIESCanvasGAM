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
"fat", "obese", "sex", "ass", "damn", "hell",
"poop", "pee", "butt", "boob", "dumb", "stupid"
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

capital = random.choice(string.ascii_uppercase)
digits = ''.join(random.choices(string.digits, k=DIGITS_AT_END))

password = capital + with_symbol + digits
return password

def generate_unique_passwords(n):
passwords = set()
while len(passwords) < n:
passwords.add(generate_password())
return sorted(passwords)

# --------- RUN + EXPORT ----------
passwords = generate_unique_passwords(TOTAL_PASSWORDS)

with open("student_passwords.csv", "w") as f:
    for p in passwords:
        f.write(p + "\n")

print(f"Generated {len(passwords)} passwords.")