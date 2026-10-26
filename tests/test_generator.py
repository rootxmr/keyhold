import string

import pytest

from keyhold import generator as g


def test_password_length_and_classes():
    for _ in range(200):
        pw = g.generate_password(12).value
        assert len(pw) == 12
        assert any(c in string.ascii_lowercase for c in pw)
        assert any(c in string.ascii_uppercase for c in pw)
        assert any(c in string.digits for c in pw)
        assert any(c in g.SYMBOLS for c in pw)


def test_password_respects_options():
    pw = g.generate_password(500, symbols=False, upper=False, exclude_ambiguous=True).value
    assert set(pw) <= set(string.ascii_lowercase + string.digits) - g.AMBIGUOUS


def test_password_entropy():
    result = g.generate_password(20, upper=False, symbols=False, digits=False)
    assert result.entropy == pytest.approx(20 * 4.7004, rel=0.001)


def test_password_errors():
    with pytest.raises(ValueError):
        g.generate_password(10, lower=False, upper=False, digits=False, symbols=False)
    with pytest.raises(ValueError):
        g.generate_password(2)


def test_passphrase():
    words = set(g.eff_words())
    assert len(words) == 7776
    result = g.generate_passphrase(7, separator=" ")
    assert len(result.value.split(" ")) == 7
    assert all(w in words for w in result.value.split(" "))
    assert result.entropy == pytest.approx(7 * 12.925, rel=0.001)


def test_passphrase_capitalize_and_number():
    parts = g.generate_passphrase(5, capitalize=True, add_number=True).value.split("-")
    assert all(p[0].isupper() for p in parts)
    assert sum(p[-1].isdigit() for p in parts) == 1


# Official BIP39 test vectors (trezor/python-mnemonic vectors.json)
@pytest.mark.parametrize(
    "entropy_hex, mnemonic",
    [
        ("00" * 16, "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"),
        ("7f" * 16, "legal winner thank year wave sausage worth useful legal winner thank yellow"),
        ("ff" * 16, "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong"),
        ("00" * 32, " ".join(["abandon"] * 23 + ["art"])),
        ("ff" * 32, " ".join(["zoo"] * 23 + ["vote"])),
    ],
)
def test_bip39_vectors(entropy_hex, mnemonic):
    assert g.entropy_to_mnemonic(bytes.fromhex(entropy_hex)) == mnemonic
    assert g.is_valid_mnemonic(mnemonic)


@pytest.mark.parametrize("words", g.SEED_WORD_COUNTS)
def test_seed_phrase(words):
    result = g.generate_seed_phrase(words)
    assert len(result.value.split()) == words
    assert g.is_valid_mnemonic(result.value)
    assert result.entropy == words * 11 * 32 // 33


def test_invalid_mnemonic():
    assert not g.is_valid_mnemonic("abandon " * 12)
    assert not g.is_valid_mnemonic("notaword " * 12)
    with pytest.raises(ValueError):
        g.generate_seed_phrase(13)


def test_pin_and_hex():
    pin = g.generate_pin(8).value
    assert len(pin) == 8 and pin.isdigit()
    key = g.generate_hex(32)
    assert len(key.value) == 64 and key.entropy == 256
    int(key.value, 16)


def test_strength():
    assert g.estimate_entropy("") == 0
    assert g.strength_label(g.estimate_entropy("password")) == "Weak"
    assert g.estimate_entropy("aaaaaaaaaaaaaaaaaaaa") < g.estimate_entropy("correct-horse-battery-staple")
