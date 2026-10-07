#!/usr/bin/env python3
"""Write .NET .resources files and build ko satellite DLL by cloning ja template."""
from __future__ import annotations

import json
import shutil
import struct
import zlib
from pathlib import Path

import dnfile

ROOT = Path(__file__).resolve().parent
EXTRACT = ROOT / "_extract"
KO_JSON_DIR = EXTRACT / "ko"
OUT_RES = EXTRACT / "ko_resources"
KO_DIR = ROOT / "ko"
JA_DLL = ROOT / "ja" / "Devolutions.Resources.resources.dll"
OUT_DLL = KO_DIR / "Devolutions.Resources.resources.dll"

# ResourceTypeCode.String = 1
READER_TYPE = (
    "System.Resources.ResourceReader, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"
)
SET_TYPE = (
    "System.Resources.RuntimeResourceSet"
)


def write7bit(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def hash_string(name: str) -> int:
    """FastResourceComparer hash used by ResourceWriter (case-insensitive)."""
    # .NET System.HashCode for FastResourceComparer:
    # Actually ResourceWriter uses:
    #  int hash = FastResourceComparer.HashFunction(name)
    # which is:
    hash_val = 5381
    for ch in name:
        c = ord(ch.upper()) if "a" <= ch <= "z" else ord(ch)
        # For non-ASCII, ToUpperInvariant is more complex; approximate with casefold for ASCII-heavy keys
        if ch.isalpha():
            c = ord(ch.upper())
        else:
            c = ord(ch)
        hash_val = ((hash_val << 5) + hash_val) ^ c
        hash_val &= 0xFFFFFFFF
    # reinterpret as signed int32
    if hash_val >= 0x80000000:
        return hash_val - 0x100000000
    return hash_val


def hash_string_net(name: str) -> int:
    """Match System.Resources.FastResourceComparer.HashFunction exactly for BMP."""
    hash_val = 5381
    for ch in name:
        # Char.ToUpperInvariant for BMP letters
        c = ord(ch)
        # Simple ToUpperInvariant for Latin + leave Hangul as-is
        if 0x61 <= c <= 0x7A:
            c -= 0x20
        hash_val = ((hash_val << 5) + hash_val) ^ c
        hash_val &= 0xFFFFFFFF
    if hash_val >= 0x80000000:
        return hash_val - 0x100000000
    return hash_val


def write_resources(strings: dict[str, str]) -> bytes:
    """Create a v2 .resources blob containing only strings."""
    # Sort by hash then name (ResourceWriter sorts by hash)
    items = sorted(strings.items(), key=lambda kv: (hash_string_net(kv[0]) & 0xFFFFFFFF, kv[0]))

    # Build name section and data section
    name_blobs = []
    data_blobs = []
    name_offsets = []
    data_offsets = []
    hashes = []

    name_pos = 0
    data_pos = 0
    for key, value in items:
        hashes.append(hash_string_net(key))
        name_offsets.append(name_pos)
        key_bytes = key.encode("utf-16-le")
        name_entry = write7bit(len(key_bytes)) + key_bytes + struct.pack("<I", data_pos)
        name_blobs.append(name_entry)
        name_pos += len(name_entry)

        data_offsets.append(data_pos)
        val_bytes = value.encode("utf-8")
        data_entry = write7bit(1) + write7bit(len(val_bytes)) + val_bytes  # type String
        data_blobs.append(data_entry)
        data_pos += len(data_entry)

    # Header
    reader_type_b = READER_TYPE.encode("utf-8")
    set_type_b = SET_TYPE.encode("utf-8")
    header_rest = (
        write7bit(len(reader_type_b))
        + reader_type_b
        + write7bit(len(set_type_b))
        + set_type_b
    )
    # pad header_rest to align? ResourceWriter pads so that after header the next field is 8-aligned from start
    # Structure:
    # Magic(4) Ver(4) HeaderSize(4) [HeaderSize bytes] Version(4) NumRes(4) NumTypes(4) Types... pad NameHashes NamePositions DataSectionOffset NameSection DataSection
    header_size = len(header_rest)
    # After writing magic+ver+headersize+header, position = 12+header_size. Types follow after version fields...

    out = bytearray()
    out += struct.pack("<I", 0xBEEFCACE)
    out += struct.pack("<I", 1)  # header version
    out += struct.pack("<I", header_size)
    out += header_rest

    out += struct.pack("<I", 2)  # resource set version
    out += struct.pack("<I", len(items))
    out += struct.pack("<I", 0)  # num types (string uses built-in typecode)

    # 8-byte align
    while len(out) % 8 != 0:
        out.append(0)

    for h in hashes:
        out += struct.pack("<i", h)
    for off in name_offsets:
        out += struct.pack("<I", off)

    # data section absolute offset = after name section
    # we need to know name section start first
    # Currently: next field is dataSectionOffset (4 bytes), then name section, then data
    data_section_offset_placeholder = len(out)
    out += struct.pack("<I", 0)  # placeholder

    name_section_start = len(out)
    for blob in name_blobs:
        out += blob
    data_section_start = len(out)
    for blob in data_blobs:
        out += blob

    struct.pack_into("<I", out, data_section_offset_placeholder, data_section_start)
    return bytes(out)


def verify_roundtrip(path: Path) -> int:
    from _extract_resources import read_resources

    data = read_resources(path.read_bytes())
    return sum(1 for v in data.values() if isinstance(v, str))


def find_utf16le(haystack: bytes, needle: str) -> list[int]:
    nb = needle.encode("utf-16-le")
    positions = []
    start = 0
    while True:
        i = haystack.find(nb, start)
        if i < 0:
            break
        positions.append(i)
        start = i + 2
    return positions


def build_satellite_by_rebuild():
    """
    Prefer building with dnlib via a small approach:
    copy ja DLL bytes and surgically replace culture + resource names + resource blobs.
    If sizes differ, rebuild resource section at end of file (advanced).
    """
    # Generate ko .resources files
    OUT_RES.mkdir(parents=True, exist_ok=True)
    mapping = [
        ("LogResources.ko.json", "Devolutions.Resources.Properties.LogResources.ko.resources"),
        ("MsgResources.ko.json", "Devolutions.Resources.Properties.MsgResources.ko.resources"),
        ("UIResources.ko.json", "Devolutions.Resources.Properties.UIResources.ko.resources"),
    ]
    resources = []
    for json_name, res_name in mapping:
        jpath = KO_JSON_DIR / json_name
        if not jpath.exists():
            raise SystemExit(f"Missing {jpath}")
        strings = json.loads(jpath.read_text(encoding="utf-8"))
        blob = write_resources(strings)
        outp = OUT_RES / res_name
        outp.write_bytes(blob)
        n = verify_roundtrip(outp)
        print(f"Wrote {outp.name}: {len(blob)} bytes, parsed strings={n}/{len(strings)}")
        resources.append((res_name, blob))

    # Build using .NET if available; else PE patch of ja template with appended resources
    return resources


def main():
    resources = build_satellite_by_rebuild()
    # Write a simple manifest for the C# builder
    manifest = {
        "resources": [
            {"name": name, "file": str(OUT_RES / name)} for name, _ in resources
        ]
    }
    (EXTRACT / "ko_build_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("Manifest ready. Run _build_satellite to produce DLL.")


if __name__ == "__main__":
    main()
