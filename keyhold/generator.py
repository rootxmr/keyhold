"""Password, passphrase and seed phrase generation.

All randomness comes from the `secrets` module (the OS CSPRNG).
"""

from __future__ import annotations

import hashlib
import math
import secrets
import string
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!#$%&()*+,-./:;<=>?@[]^_{|}~"
AMBIGUOUS = frozenset("Il1|O0o`'\"")

SEED_WORD_COUNTS = (12, 15, 18, 21, 24)

_rng = secrets.SystemRandom()


@dataclass(frozen=True)
class Generated:
    value: str
    entropy: float  # bits


@cache
def _wordlist(name: str) -> tuple[str, ...]:
    text = files("keyhold.wordlists").joinpath(name).read_text(encoding="utf-8")
    return tuple(w for w in (line.strip() for line in text.splitlines()) if w)


def eff_words() -> tuple[str, ...]:
    return _wordlist("eff_large.txt")


def bip39_words() -> tuple[str, ...]:
    words = _wordlist("bip39_english.txt")
    assert len(words) == 2048
    return words


# -- random character passwords ---------------------------------------------


def generate_password(
    length: int = 20,
    *,
    lower: bool = True,
    upper: bool = True,
    digits: bool = True,
    symbols: bool = True,
    exclude_ambiguous: bool = False,
) -> Generated:
    """Random password guaranteed to contain at least one of each enabled class."""
    classes = [
        chars for enabled, chars in ((lower, LOWER), (upper, UPPER), (digits, DIGITS), (symbols, SYMBOLS)) if enabled
    ]
    if exclude_ambiguous:
        classes = [("".join(c for c in chars if c not in AMBIGUOUS)) for chars in classes]
    if not classes:
        raise ValueError("Select at least one character set")
    if length < len(classes):
        raise ValueError(f"Length must be at least {len(classes)} for the selected sets")

    pool = "".join(classes)
    chars = [secrets.choice(c) for c in classes]
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    _rng.shuffle(chars)
    return Generated("".join(chars), length * math.log2(len(pool)))


# -- word-based --------------------------------------------------------------


def generate_passphrase(
    words: int = 6,
    *,
    separator: str = "-",
    capitalize: bool = False,
    add_number: bool = False,
) -> Generated:
    """Diceware-style passphrase from the EFF large wordlist (12.9 bits/word)."""
    if words < 1:
        raise ValueError("Use at least one word")
    wordlist = eff_words()
    chosen = [secrets.choice(wordlist) for _ in range(words)]
    if capitalize:
        chosen = [w.capitalize() for w in chosen]
    entropy = words * math.log2(len(wordlist))
    if add_number:
        i = secrets.randbelow(words)
        chosen[i] += str(secrets.randbelow(10))
        entropy += math.log2(10 * words)
    return Generated(separator.join(chosen), entropy)


def entropy_to_mnemonic(entropy: bytes) -> str:
    """Encode entropy as a BIP39 mnemonic (with checksum)."""
    if len(entropy) not in (16, 20, 24, 28, 32):
        raise ValueError("BIP39 entropy must be 128-256 bits in 32-bit steps")
    ent_bits = len(entropy) * 8
    cs_bits = ent_bits // 32
    checksum = hashlib.sha256(entropy).digest()[0] >> (8 - cs_bits)
    bits = (int.from_bytes(entropy, "big") << cs_bits) | checksum
    total = ent_bits + cs_bits
    wordlist = bip39_words()
    return " ".join(wordlist[(bits >> (total - 11 * (i + 1))) & 0x7FF] for i in range(total // 11))


def is_valid_mnemonic(phrase: str) -> bool:
    """Check that a phrase is made of BIP39 words with a correct checksum."""
    words = phrase.split()
    if len(words) not in SEED_WORD_COUNTS:
        return False
    index = {w: i for i, w in enumerate(bip39_words())}
    try:
        bits = 0
        for w in words:
            bits = (bits << 11) | index[w]
    except KeyError:
        return False
    total = len(words) * 11
    cs_bits = total // 33
    entropy = (bits >> cs_bits).to_bytes((total - cs_bits) // 8, "big")
    return entropy_to_mnemonic(entropy) == " ".join(words)


def generate_seed_phrase(words: int = 24) -> Generated:
    """BIP39-compatible mnemonic (12-24 words)."""
    if words not in SEED_WORD_COUNTS:
        raise ValueError(f"Word count must be one of {SEED_WORD_COUNTS}")
    nbytes = words * 11 * 32 // 33 // 8
    return Generated(entropy_to_mnemonic(secrets.token_bytes(nbytes)), nbytes * 8)


# -- other formats -----------------------------------------------------------


def generate_pin(length: int = 6) -> Generated:
    if length < 1:
        raise ValueError("PIN length must be at least 1")
    return Generated("".join(secrets.choice(DIGITS) for _ in range(length)), length * math.log2(10))


def generate_hex(nbytes: int = 32) -> Generated:
    if nbytes < 1:
        raise ValueError("Key size must be at least 1 byte")
    return Generated(secrets.token_hex(nbytes), nbytes * 8)


# -- strength ----------------------------------------------------------------


def estimate_entropy(password: str) -> float:
    """Rough entropy estimate for a human-chosen password.

    Character-pool based, with a penalty for repeated characters. It is an
    upper bound at best; humans pick predictable passwords.
    """
    if not password:
        return 0.0
    pool = 0
    if any(c in LOWER for c in password):
        pool += 26
    if any(c in UPPER for c in password):
        pool += 26
    if any(c in DIGITS for c in password):
        pool += 10
    if any(c in string.punctuation or c == " " for c in password):
        pool += 33
    if any(ord(c) > 127 for c in password):
        pool += 100
    unique = len(set(password))
    effective_length = min(len(password), unique * 2)
    return effective_length * math.log2(max(pool, 2))


def strength_label(bits: float) -> str:
    if bits < 40:
        return "Weak"
    if bits < 64:
        return "Fair"
    if bits < 100:
        return "Strong"
    return "Very strong"
