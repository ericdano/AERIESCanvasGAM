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
OFFENSIVE_WORDS = ["word1", "word2", "word3"] # Add inappropriate substrings here

def create_password():
"""Generates a single, unique password based on the specified rules."""
while True:
# --- 1. Create a pronounceable "word" base (CVCVCV) ---
word = ""
for i in range(3):
word += random.choice(CONSONANTS)
word += random.choice(VOWELS)

# Ensure the word is not offensive and has a replaceable letter
is_offensive = any(bad_word in word for bad_word in OFFENSIVE_WORDS)
has_replaceable = any(char in word for char in REPLACEABLE_LETTERS)

if not is_offensive and has_replaceable:
# --- 2. Substitute a special symbol ---
replaceable_chars = [char for char in word if char in REPLACEABLE_LETTERS]
char_to_replace = random.choice(replaceable_chars)
symbol = SYMBOL_MAP[char_to_replace]

# Replace the first occurrence of the chosen character
word_with_symbol = word.replace(char_to_replace, symbol, 1)

# Capitalize the first letter
final_word = word_with_symbol.capitalize()

# --- 3. Append three numbers ---
three_digits = f"{random.randint(0, 999):03d}"

return final_word + three_digits

# --- Main Generation Loop ---
password_list = set()
while len(password_list) < 6000:
new_password = create_password()
password_list.add(new_password)

# Print or save the list
# for pwd in sorted(list(password_list)):
# print(pwd)

# To save to a file:
# with open("passwords.txt", "w") as f:
# for pwd in sorted(list(password_list)):
# f.write(pwd + "\n")