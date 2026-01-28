import random
import string

# --- 1. Define Character Sets ---
VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnprstvw"
# Letters that can be replaced by a symbol
REPLACEABLE_LETTERS = "asihle"
SYMBOL_MAP = {
    'a': '@',
    's': '$',
    'i': '!',
    'l': '!',
    'h': '#',
    'e': '&'
    }
# --- 4. Add words to this list to filter them out ---
OFFENSIVE_WORDS = [
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
]
def create_password():
    """Generates a single, unique password based on the specified rules."""
    while True:
        # --- 1. Create a base word ---
        word = ""
        for i in range(3):
            word += random.choice(CONSONANTS)
            word += random.choice(VOWELS)

        is_offensive = any(bad_word in word for bad_word in OFFENSIVE_WORDS)
        has_replaceable = any(char in word for char in REPLACEABLE_LETTERS)

        # Everything from here down must stay inside the 'if' block
        if not is_offensive and has_replaceable:
            # --- 2. Substitute a special symbol ---
            replaceable_chars = [char for char in word if char in REPLACEABLE_LETTERS]
            char_to_replace = random.choice(replaceable_chars)
            symbol = SYMBOL_MAP[char_to_replace]

            # Replace the symbol
            word_with_symbol = word.replace(char_to_replace, symbol, 1)

            # Capitalize
            final_word = word_with_symbol.capitalize()

            # --- 3. Append digits ---
            three_digits = f"{random.randint(0, 999):03d}"

            # Return ends the while loop and the function
            return final_word + three_digits

# --- Main Generation Loop ---
password_list = set()
while len(password_list) < 6000:
    new_password = create_password()
    password_list.add(new_password)

# Print or save the list
for pwd in sorted(list(password_list)):
    print(pwd)

    # To save to a file:
    # with open("passwords.txt", "w") as f:
    # for pwd in sorted(list(password_list)):
    # f.write(pwd + "\n")