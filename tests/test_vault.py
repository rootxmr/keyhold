import os

import pytest

from keyhold.crypto import AuthenticationError, VaultError
from keyhold.vault import Entry, Vault


@pytest.fixture
def vault(tmp_path, fast_kdf):
    return Vault.create(tmp_path / "test.keyhold", "master pw", params=fast_kdf)


def test_create_and_reopen(vault):
    vault.add(Entry(title="Mail", username="me@example.com", password="s3cret", notes="ünïcode ✓"))
    reopened = Vault.open(vault.path, "master pw")
    assert len(reopened.entries) == 1
    e = reopened.entries[0]
    assert (e.title, e.username, e.password, e.notes) == ("Mail", "me@example.com", "s3cret", "ünïcode ✓")


def test_file_contains_no_plaintext(vault):
    vault.add(Entry(title="Bank", password="very-recognisable-password"))
    raw = vault.path.read_bytes()
    assert b"Bank" not in raw and b"very-recognisable-password" not in raw


def test_create_refuses_to_overwrite(vault, fast_kdf):
    with pytest.raises(FileExistsError):
        Vault.create(vault.path, "other", params=fast_kdf)


def test_update_and_delete(vault):
    e = vault.add(Entry(title="Old"))
    created = e.created
    vault.update(e.id, title="New", password="pw")
    assert Vault.open(vault.path, "master pw").entries[0].title == "New"
    assert vault.get(e.id).created == created
    with pytest.raises(AttributeError):
        vault.update(e.id, id="hijack")
    vault.delete(e.id)
    assert Vault.open(vault.path, "master pw").entries == []


def test_search(vault):
    vault.add(Entry(title="GitHub", username="octo"))
    vault.add(Entry(title="bank", url="bank.example"))
    assert [e.title for e in vault.search("")] == ["bank", "GitHub"]
    assert [e.title for e in vault.search("OCTO")] == ["GitHub"]
    assert [e.title for e in vault.search("example")] == ["bank"]


def test_backup_is_kept(vault):
    vault.add(Entry(title="one"))
    vault.add(Entry(title="two"))
    backup = vault.path.with_name(vault.path.name + ".bak")
    assert len(Vault.open(backup, "master pw").entries) == 1


def test_failed_save_rolls_back(vault, monkeypatch):
    vault.add(Entry(title="kept"))

    def broken_save():
        raise OSError("disk full")

    monkeypatch.setattr(vault, "save", broken_save)
    with pytest.raises(OSError):
        vault.add(Entry(title="lost"))
    with pytest.raises(OSError):
        vault.delete(vault.entries[0].id)
    assert [e.title for e in vault.entries] == ["kept"]


def test_change_master_key_rekeys_backup(vault):
    vault.add(Entry(title="x"))
    vault.change_master_key("new password", b"keyfile")
    for path in (vault.path, vault.path.with_name(vault.path.name + ".bak")):
        with pytest.raises(AuthenticationError):
            Vault.open(path, "master pw")
        assert Vault.open(path, "new password", b"keyfile").entries[0].title == "x"


def test_no_temp_file_left(vault):
    vault.add(Entry(title="x"))
    assert sorted(os.listdir(vault.path.parent)) == ["test.keyhold", "test.keyhold.bak"]


def test_locked_vault_refuses_to_save(vault):
    vault.add(Entry(title="keep me"))
    vault.lock()
    with pytest.raises(VaultError):
        vault.save()
    with pytest.raises(VaultError):
        vault.change_master_key("new")
    assert Vault.open(vault.path, "master pw").entries[0].title == "keep me"
