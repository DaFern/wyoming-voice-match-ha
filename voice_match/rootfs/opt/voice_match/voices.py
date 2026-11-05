"""Account-owned voice metadata and narrowly scoped biometric data removal."""

import json
import os
from pathlib import Path
import re
import uuid


class Denied(Exception):
    pass


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", value):
        raise ValueError("Invalid voice ID")
    return value


def display_name(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 80 or not value.isprintable():
        raise ValueError("Enter a name between 1 and 80 characters")
    return value.strip()


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as output:
        json.dump(value, output)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_voiceprint(path):
    import numpy as np
    value = np.load(path, allow_pickle=False)
    if (value.shape != (192,) or not np.issubdtype(value.dtype, np.floating)
            or not np.isfinite(value).all()):
        raise ValueError("Generated voiceprint is invalid; previous voice was kept")
    norm = np.linalg.norm(value)
    if not np.isfinite(norm) or norm < 0.01:
        raise ValueError("Generated voiceprint is invalid; previous voice was kept")


class VoiceStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = self.root / "profiles.json"
        self.profiles = json.loads(self.path.read_text()) if self.path.exists() else {}
        for voice_id in self.profiles:
            safe_id(voice_id)
            self.profiles[voice_id].setdefault("personal_instructions", "")
            self.profiles[voice_id].setdefault("context_version", uuid.uuid4().hex)
        # Never infer ownership from names or first visitor. Legacy profiles are
        # visible only to administrators until explicitly assigned.
        for path in (self.root / "voiceprints").glob("*.npy"):
            try:
                voice_id = safe_id(path.stem)
            except ValueError:
                continue
            if voice_id not in self.profiles:
                self.profiles[voice_id] = {"name": voice_id, "owner": None,
                                          "personal_instructions": "", "context_version": uuid.uuid4().hex}
        self.save()

    def save(self):
        atomic_json(self.path, self.profiles)

    def get(self, voice_id, actor):
        profile = self.profiles.get(safe_id(voice_id))
        if profile is None or (not actor["admin"] and profile["owner"] != actor["id"]):
            raise Denied("This voice is not available to your account")
        return profile

    def visible(self, actor):
        return [dict(id=key, **profile) for key, profile in self.profiles.items()
                if actor["admin"] or profile["owner"] == actor["id"]]

    def create(self, name, owner):
        if len(self.profiles) >= 50:
            raise ValueError("Maximum of 50 voice profiles reached")
        if any(item["owner"] == owner for item in self.profiles.values()):
            raise ValueError("This account already has a voice. Choose Re-enrol instead")
        voice_id = "v" + uuid.uuid4().hex
        self.profiles[voice_id] = {"name": display_name(name), "owner": owner,
                                  "personal_instructions": "", "context_version": uuid.uuid4().hex}
        self.save()
        return voice_id

    def assign(self, voice_id, owner, actor):
        if not actor["admin"]:
            raise Denied("Only administrators can assign voice ownership")
        profile = self.get(voice_id, actor)
        if any(key != voice_id and item["owner"] == owner for key, item in self.profiles.items()):
            raise ValueError("That account already has a voice")
        if profile["owner"] != owner:
            profile["owner"] = owner
            # Do not carry one person's preferences or active context to a new owner.
            profile["personal_instructions"] = ""
            profile["context_version"] = uuid.uuid4().hex
        self.save()

    def _files(self, voice_id):
        safe_id(voice_id)
        for directory in (self.root / "enrollment" / voice_id, self.root / "enrollment_work" / voice_id):
            # Do not follow directory or file symlinks, including ancestors.
            if directory.parent.is_symlink() or directory.is_symlink():
                raise ValueError("Unsafe recording directory; cleanup refused")
            if not directory.exists():
                continue
            for base, directories, files in os.walk(directory, followlinks=False):
                directories[:] = [name for name in directories if not (Path(base) / name).is_symlink()]
                for name in files:
                    path = Path(base) / name
                    if not path.is_symlink() and path.suffix in {".wav", ".part", ".npy"}:
                        yield path

    def recording_bytes(self, voice_id):
        return sum(path.stat().st_size for path in self._files(voice_id))

    def discard_session(self, voice_id, session):
        """Narrow unfinished-session removal, including only its staging hardlinks."""
        safe_id(voice_id)
        if not isinstance(session, str) or re.fullmatch(r"[0-9a-f]{32}", session) is None:
            raise ValueError("Invalid learning session")
        directory = self.root / "enrollment" / voice_id / session
        staging = self.root / "enrollment_work" / voice_id
        for path in (self.root, directory.parent.parent, directory.parent, directory,
                     staging.parent, staging):
            if path.is_symlink():
                raise ValueError("Unsafe recording directory; discard refused")
        if (directory / "COMPLETE").exists():
            raise ValueError("Completed learning cannot be discarded")
        paths = []
        if directory.exists():
            for base, directories, files in os.walk(directory, followlinks=False):
                if any((Path(base) / name).is_symlink() for name in [*directories, *files]):
                    raise ValueError("Unsafe recording link; discard refused")
                for name in files:
                    path = Path(base) / name
                    if path.suffix not in {".wav", ".part", ".npy"} or not path.is_file():
                        raise ValueError("Unexpected session file; discard refused")
                    paths.append(path)
        # Never remove staging files by filename alone: they could belong to a
        # different generation. Match this session's actual filesystem objects.
        inodes = {(path.stat().st_dev, path.stat().st_ino) for path in paths}
        links = []
        if staging.exists():
            for path in staging.iterdir():
                if path.is_symlink():
                    raise ValueError("Unsafe staging link; discard refused")
                if path.is_file() and (path.stat().st_dev, path.stat().st_ino) in inodes:
                    links.append(path)
        for path in [*links, *paths]:
            path.unlink()

    def cleanup(self, voice_id):
        # Removes BOTH hard links created by legacy enrolment. Never touches
        # /data/voiceprints, other people, models, or old external backups.
        for path in list(self._files(voice_id)):
            path.unlink()

    def delete(self, voice_id, actor):
        self.get(voice_id, actor)
        self.cleanup(voice_id)
        directory = self.root / "voiceprints"
        if directory.is_symlink():
            raise ValueError("Unsafe voiceprint directory; deletion refused")
        (directory / f"{voice_id}.npy").unlink(missing_ok=True)
        del self.profiles[voice_id]
        self.save()
