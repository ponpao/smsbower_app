# -*- coding: utf-8 -*-
"""Profile/group persistence.

Data lives next to the executable in ./data:
    data/profiles.json          groups + profiles (schema-versioned)
    data/settings.json          language, chrome_path, create_gmail flag
    data/backups/               rotating auto-backups of profiles.json
    data/chrome_profiles/<key>  Chrome --user-data-dir folders
"""

import json
import os
import shutil
import time
import uuid

SCHEMA_VERSION = 2
BACKUPS_TO_KEEP = 20

DEFAULT_GROUP_COLORS = [
    "#4f8ef7", "#34c759", "#ff9500", "#ff3b30", "#af52de",
    "#00c7be", "#ff2d92", "#8e8e93", "#a2845e", "#5856d6",
]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class ProfileStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.profiles_path = os.path.join(data_dir, "profiles.json")
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.backups_dir = os.path.join(data_dir, "backups")
        self.chrome_dir = os.path.join(data_dir, "chrome_profiles")
        os.makedirs(self.backups_dir, exist_ok=True)
        os.makedirs(self.chrome_dir, exist_ok=True)
        self.data = self._load_profiles()
        self.settings = self._load_settings()

    # ---------- load / migrate ----------

    def _load_profiles(self) -> dict:
        if not os.path.exists(self.profiles_path):
            data = {"schema_version": SCHEMA_VERSION, "groups": [], "profiles": []}
            self._write(self.profiles_path, data)
            return data
        with open(self.profiles_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        migrated = self._migrate(data)
        if migrated is not data or data.get("schema_version") != SCHEMA_VERSION:
            # keep a pre-migration copy before rewriting the file
            self._backup(tag="pre-migration")
            self._write(self.profiles_path, migrated)
        return migrated

    def _migrate(self, data) -> dict:
        # v1 (hypothetical original format): a bare list of profile dicts,
        # group stored as a name string. Normalize into the v2 shape.
        if isinstance(data, list):
            data = {"schema_version": 1, "groups": [], "profiles": data}
        version = data.get("schema_version", 1)
        if version >= SCHEMA_VERSION:
            data.setdefault("groups", [])
            data.setdefault("profiles", [])
            return data
        group_names = []
        for p in data.get("profiles", []):
            g = p.get("group", "")
            if g and g not in group_names:
                group_names.append(g)
        groups = [
            {"id": new_id(), "name": name, "color": DEFAULT_GROUP_COLORS[i % len(DEFAULT_GROUP_COLORS)], "order": i}
            for i, name in enumerate(group_names)
        ]
        by_name = {g["name"]: g["id"] for g in groups}
        profiles = []
        for p in data.get("profiles", []):
            profiles.append({
                "id": p.get("id") or new_id(),
                "name": p.get("name", ""),
                "key": p.get("key", ""),
                "gmail": p.get("gmail", ""),
                "password": p.get("password", ""),
                "favorite": bool(p.get("favorite")),
                "group_id": by_name.get(p.get("group", ""), ""),
                "launch_url": p.get("launch_url", ""),
                "created_at": p.get("created_at", _now()),
                "last_used": p.get("last_used", ""),
            })
        return {"schema_version": SCHEMA_VERSION, "groups": groups, "profiles": profiles}

    def _load_settings(self) -> dict:
        defaults = {"language": "km", "chrome_path": "", "create_gmail": False}
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    defaults.update(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        return defaults

    # ---------- save / backup ----------

    def _write(self, path: str, data) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _backup(self, tag: str = "auto") -> None:
        if not os.path.exists(self.profiles_path):
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(self.backups_dir, f"profiles_{stamp}_{tag}.json")
        n = 1
        while os.path.exists(dest):  # several saves within the same second
            dest = os.path.join(self.backups_dir, f"profiles_{stamp}_{n:02d}_{tag}.json")
            n += 1
        try:
            shutil.copy2(self.profiles_path, dest)
        except OSError:
            return
        backups = sorted(
            f for f in os.listdir(self.backups_dir)
            if f.startswith("profiles_") and f.endswith(".json")
        )
        for old in backups[:-BACKUPS_TO_KEEP]:
            try:
                os.remove(os.path.join(self.backups_dir, old))
            except OSError:
                pass

    def save(self) -> None:
        """Auto-backup on every save: cheap insurance against data loss."""
        self._backup()
        self._write(self.profiles_path, self.data)

    def save_settings(self) -> None:
        self._write(self.settings_path, self.settings)

    # ---------- groups ----------

    @property
    def groups(self) -> list:
        return sorted(self.data["groups"], key=lambda g: g.get("order", 0))

    def group_by_id(self, group_id: str):
        return next((g for g in self.data["groups"] if g["id"] == group_id), None)

    def group_name_taken(self, name: str, exclude_id: str = "") -> bool:
        name = name.strip().casefold()
        return any(
            g["name"].strip().casefold() == name and g["id"] != exclude_id
            for g in self.data["groups"]
        )

    def add_group(self, name: str, color: str = "") -> dict:
        color = color or DEFAULT_GROUP_COLORS[len(self.data["groups"]) % len(DEFAULT_GROUP_COLORS)]
        group = {"id": new_id(), "name": name.strip(), "color": color,
                 "order": len(self.data["groups"])}
        self.data["groups"].append(group)
        self.save()
        return group

    def update_group(self, group_id: str, name: str = None, color: str = None) -> None:
        g = self.group_by_id(group_id)
        if not g:
            return
        if name is not None:
            g["name"] = name.strip()
        if color is not None:
            g["color"] = color
        self.save()

    def delete_group(self, group_id: str, delete_profiles: bool) -> list:
        """Remove a group. Returns the profiles that were inside it.

        delete_profiles=False moves them back to uncategorized ("All");
        True removes their records too (disk folders are handled by the
        caller only after explicit user confirmation — never silently).
        """
        inside = [p for p in self.data["profiles"] if p.get("group_id") == group_id]
        self.data["groups"] = [g for g in self.data["groups"] if g["id"] != group_id]
        if delete_profiles:
            ids = {p["id"] for p in inside}
            self.data["profiles"] = [p for p in self.data["profiles"] if p["id"] not in ids]
        else:
            for p in inside:
                p["group_id"] = ""
        for i, g in enumerate(self.groups):
            g["order"] = i
        self.save()
        return inside

    def reorder_groups(self, ordered_ids: list) -> None:
        order = {gid: i for i, gid in enumerate(ordered_ids)}
        for g in self.data["groups"]:
            g["order"] = order.get(g["id"], g.get("order", 0))
        self.save()

    def group_count(self, group_id: str) -> int:
        return sum(1 for p in self.data["profiles"] if p.get("group_id") == group_id)

    # ---------- profiles ----------

    @property
    def profiles(self) -> list:
        return self.data["profiles"]

    def profile_by_id(self, pid: str):
        return next((p for p in self.data["profiles"] if p["id"] == pid), None)

    def next_profile_key(self) -> str:
        used = {p.get("key", "") for p in self.data["profiles"]}
        n = 1
        while f"Profile {n}" in used:
            n += 1
        return f"Profile {n}"

    def add_profile(self, **fields) -> dict:
        profile = {
            "id": new_id(),
            "name": fields.get("name", ""),
            "key": fields.get("key") or self.next_profile_key(),
            "gmail": fields.get("gmail", ""),
            "password": fields.get("password", ""),
            "favorite": bool(fields.get("favorite")),
            "group_id": fields.get("group_id", ""),
            "launch_url": fields.get("launch_url", ""),
            "created_at": _now(),
            "last_used": "",
        }
        self.data["profiles"].append(profile)
        self.save()
        return profile

    def update_profile(self, pid: str, **fields) -> None:
        p = self.profile_by_id(pid)
        if not p:
            return
        for k in ("name", "key", "gmail", "password", "favorite", "group_id", "launch_url", "last_used"):
            if k in fields:
                p[k] = fields[k]
        self.save()

    def delete_profiles(self, pids: list) -> None:
        pids = set(pids)
        self.data["profiles"] = [p for p in self.data["profiles"] if p["id"] not in pids]
        self.save()

    def move_profiles_to_group(self, pids: list, group_id: str) -> None:
        pids = set(pids)
        for p in self.data["profiles"]:
            if p["id"] in pids:
                p["group_id"] = group_id
        self.save()

    def user_data_dir(self, profile: dict) -> str:
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in profile.get("key") or profile["id"])
        return os.path.join(self.chrome_dir, safe.strip() or profile["id"])

    def delete_profile_disk_data(self, profile: dict) -> None:
        """Only ever called after an explicit user confirmation dialog."""
        path = self.user_data_dir(profile)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)

    # ---------- import / export ----------

    def export_profiles(self, profiles: list, path: str) -> None:
        if path.lower().endswith(".csv"):
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "key", "gmail", "password", "group", "favorite", "launch_url"])
                for p in profiles:
                    g = self.group_by_id(p.get("group_id", ""))
                    writer.writerow([p["name"], p["key"], p["gmail"], p["password"],
                                     g["name"] if g else "", "1" if p.get("favorite") else "0",
                                     p.get("launch_url", "")])
        else:
            payload = {"schema_version": SCHEMA_VERSION,
                       "groups": [g for g in self.groups],
                       "profiles": profiles}
            self._write(path, payload)

    def import_profiles(self, path: str) -> int:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = self._migrate(data)
        by_name = {g["name"].casefold(): g["id"] for g in self.data["groups"]}
        incoming_groups = {g["id"]: g for g in data.get("groups", [])}
        count = 0
        existing_keys = {p.get("key") for p in self.data["profiles"]}
        for p in data.get("profiles", []):
            gid = ""
            src_group = incoming_groups.get(p.get("group_id", ""))
            if src_group:
                gid = by_name.get(src_group["name"].casefold())
                if gid is None:
                    new_group = self.add_group(src_group["name"], src_group.get("color", ""))
                    gid = new_group["id"]
                    by_name[new_group["name"].casefold()] = gid
            key = p.get("key", "")
            if not key or key in existing_keys:
                key = self.next_profile_key()
            existing_keys.add(key)
            self.add_profile(name=p.get("name", ""), key=key, gmail=p.get("gmail", ""),
                             password=p.get("password", ""), favorite=p.get("favorite"),
                             group_id=gid, launch_url=p.get("launch_url", ""))
            count += 1
        return count
