import pytest

from keyhold.crypto import KdfParams

# The minimum Argon2id cost accepted by the vault format, so tests run fast.
FAST = KdfParams(opslimit=1, memlimit=8 * 1024 * 1024)


@pytest.fixture
def fast_kdf() -> KdfParams:
    return FAST
