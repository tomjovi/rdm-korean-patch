#!/usr/bin/env python3
"""
Build ko satellite DLL by cloning the ja satellite PE and replacing:
- Assembly culture ja -> ko
- Manifest resource names *.ja.resources -> *.ko.resources  
- Manifest resource blobs with newly written Korean .resources
"""
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path

import dnfile

ROOT = Path(__file__).resolve().parent
EXTRACT = ROOT / "_extract"
KO_JSON = EXTRACT / "ko"
OUT_RES = EXTRACT / "ko_resources"
JA_DLL = ROOT / "ja" / "Devolutions.Resources.resources.dll"
KO_DLL = ROOT / "ko" / "Devolutions.Resources.resources.dll"

READER_TYPE = (
    "System.Resources.ResourceReader, mscorlib, Version=4.0.0.0, Culture=neutral, PublicKeyToken=b77a5c561934e089"
)
SET_TYPE = "System.Resources.RuntimeResourceSet"


def write7bit(value: int) -> bytes:
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def hash_string_net(name: str) -> int:
    hash_val = 5381
    for ch in name:
        c = ord(ch)
        if 0x61 <= c <= 0x7A:
            c -= 0x20
        hash_val = ((hash_val << 5) + hash_val) ^ c
        hash_val &= 0xFFFFFFFF
    if hash_val >= 0x80000000:
        return hash_val - 0x100000000
    return hash_val


def write_resources(strings: dict[str, str]) -> bytes:
    items = sorted(
        strings.items(), key=lambda kv: (hash_string_net(kv[0]) & 0xFFFFFFFF, kv[0])
    )
    name_blobs = []
    data_blobs = []
    name_offsets = []
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
        val_bytes = value.encode("utf-8")
        data_entry = write7bit(1) + write7bit(len(val_bytes)) + val_bytes
        data_blobs.append(data_entry)
        data_pos += len(data_entry)

    reader_type_b = READER_TYPE.encode("utf-8")
    set_type_b = SET_TYPE.encode("utf-8")
    header_rest = (
        write7bit(len(reader_type_b))
        + reader_type_b
        + write7bit(len(set_type_b))
        + set_type_b
    )
    out = bytearray()
    out += struct.pack("<III", 0xBEEFCACE, 1, len(header_rest))
    out += header_rest
    out += struct.pack("<III", 2, len(items), 0)
    while len(out) % 8 != 0:
        out.append(0)
    for h in hashes:
        out += struct.pack("<i", h)
    for off in name_offsets:
        out += struct.pack("<I", off)
    data_section_offset_placeholder = len(out)
    out += struct.pack("<I", 0)
    for blob in name_blobs:
        out += blob
    data_section_start = len(out)
    for blob in data_blobs:
        out += blob
    struct.pack_into("<I", out, data_section_offset_placeholder, data_section_start)
    return bytes(out)


def replace_utf16_in_place(data: bytearray, old: str, new: str) -> int:
    if len(old) != len(new):
        raise ValueError(f"length mismatch {old!r} vs {new!r}")
    ob = old.encode("utf-16-le")
    nb = new.encode("utf-16-le")
    count = 0
    start = 0
    while True:
        i = data.find(ob, start)
        if i < 0:
            break
        data[i : i + len(ob)] = nb
        count += 1
        start = i + len(nb)
    return count


def build_resource_section(resources: list[tuple[str, bytes]]) -> tuple[bytes, list[tuple[str, int]]]:
    """
    Build CLI managed resource blob: for each resource, 4-byte length + data.
    Returns (section_bytes, [(name, offset_into_section), ...]).
    """
    section = bytearray()
    entries = []
    for name, blob in resources:
        # Align? ECMA says each resource starts at offset stored in ManifestResource;
        # length prefix is at that offset.
        # Align to 8 bytes between resources (common practice)
        while len(section) % 8 != 0:
            section.append(0)
        offset = len(section)
        section += struct.pack("<I", len(blob))
        section += blob
        entries.append((name, offset))
    return bytes(section), entries


def patch_satellite(ja_path: Path, out_path: Path, resources: list[tuple[str, bytes]]) -> None:
    """
    Strategy: copy ja DLL, replace culture/name strings of equal length,
    then overwrite the managed resources section in-place if new data fits,
    otherwise append a new resources section and update COR20 ResourcesRva/Size
    and ManifestResource offsets.
    """
    data = bytearray(ja_path.read_bytes())
    pe = dnfile.dnPE(str(ja_path))

    # Culture ja -> ko (same length)
    n1 = replace_utf16_in_place(data, "ja", "ko")
    # Also ASCII "ja" in assembly culture might be in #US as UTF-16
    # Resource names: .ja.resources -> .ko.resources
    n2 = replace_utf16_in_place(data, ".ja.resources", ".ko.resources")
    # ASCII variants in metadata heaps are UTF-16 for user strings, but
    # ManifestResource names are in #Strings (UTF-8)!
    n3 = data.replace(b".ja.resources", b".ko.resources")
    # Culture in #Strings heap as 'ja'
    # Be careful not to replace random 'ja' — Assembly culture is typically standalone
    print(f"utf16 ja->ko approx hits: {n1}, utf16 name: {n2}, utf8 name bytes replaced chunk")

    new_section, entries = build_resource_section(resources)
    old_rva = pe.net.struct.ResourcesRva
    old_size = pe.net.struct.ResourcesSize
    old_file_off = pe.get_offset_from_rva(old_rva)
    print(f"Old resources RVA={old_rva:#x} size={old_size} file_off={old_file_off:#x}")
    print(f"New resources size={len(new_section)}")

    if len(new_section) <= old_size:
        # Fit in place, zero-pad remainder
        data[old_file_off : old_file_off + len(new_section)] = new_section
        for i in range(len(new_section), old_size):
            data[old_file_off + i] = 0
        # Update ManifestResource offsets in metadata — need to patch table
        # Since we rebuilt in same order as we'll specify, update offsets
        patch_manifest_offsets(pe, data, entries)
        # Update ResourcesSize in COR20
        patch_cor20_resources_size(pe, data, len(new_section))
    else:
        # Append at end of file; requires adding/expanding a section — complex.
        # Simpler approach: expand last section or write after file and update.
        raise SystemExit(
            f"New resources ({len(new_section)}) larger than old ({old_size}). "
            "Need expand path — try building with smaller strings or implement section expand."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    print(f"Wrote {out_path} ({len(data)} bytes)")


def patch_cor20_resources_size(pe: dnfile.dnPE, data: bytearray, new_size: int) -> None:
    # Find COR20 header ResourcesSize field file offset
    # dnfile ClrStruct has get_field_absolute_offset
    try:
        off = pe.net.struct.get_field_absolute_offset("ResourcesSize")
        struct.pack_into("<I", data, off, new_size)
        print(f"Patched ResourcesSize @ {off:#x} -> {new_size}")
    except Exception as e:
        print(f"WARN: could not patch ResourcesSize: {e}")


def patch_manifest_offsets(
    pe: dnfile.dnPE, data: bytearray, entries: list[tuple[str, int]]
) -> None:
    """Patch ManifestResource.Offset values to match new layout."""
    # Map by matching ko names
    by_name = {name: off for name, off in entries}
    rows = list(pe.net.mdtables.ManifestResource)
    # ManifestResource table row layout: Offset(4) Flags(4) Name(Strings) Implementation
    # We need raw table file offset
    table = pe.net.mdtables.ManifestResource
    try:
        table_off = table.file_offset  # might exist
    except Exception:
        table_off = getattr(table, "_file_offset", None) or getattr(
            table, "fileoffset", None
        )
    if table_off is None:
        # Compute from metadata
        print("WARN: cannot locate ManifestResource table offset; offsets may be wrong if order changed")
        return

    row_size = table.sizeof() if callable(getattr(table, "sizeof", None)) else None
    if row_size is None:
        # Typical: Offset(4)+Flags(4)+Name(2or4)+Implementation(2or4)
        # Use dnfile row size
        row_size = table.row_size if hasattr(table, "row_size") else None
    print(f"ManifestResource table_off={table_off} row_size={row_size} rows={len(rows)}")

    if row_size is None:
        return

    for i, row in enumerate(rows):
        name = str(row.Name).replace(".ja.", ".ko.")
        # After our string replace, names in PE are already .ko.
        name_ko = str(row.Name)
        if name_ko.endswith(".ja.resources"):
            name_ko = name_ko.replace(".ja.resources", ".ko.resources")
        # Prefer matching by index order if names unclear
        if name_ko in by_name:
            new_off = by_name[name_ko]
        elif i < len(entries):
            new_off = entries[i][1]
        else:
            continue
        abs_off = table_off + i * row_size  # Offset is first field
        old = struct.unpack_from("<I", data, abs_off)[0]
        struct.pack_into("<I", data, abs_off, new_off)
        print(f"  row {i} {name_ko}: offset {old} -> {new_off}")


def main():
    mapping = [
        ("LogResources.ko.json", "Devolutions.Resources.Properties.LogResources.ko.resources"),
        ("MsgResources.ko.json", "Devolutions.Resources.Properties.MsgResources.ko.resources"),
        ("UIResources.ko.json", "Devolutions.Resources.Properties.UIResources.ko.resources"),
    ]
    # ja order was: Log, Msg, UI — keep same
    OUT_RES.mkdir(parents=True, exist_ok=True)
    resources: list[tuple[str, bytes]] = []
    for json_name, res_name in mapping:
        jpath = KO_JSON / json_name
        if not jpath.exists():
            raise SystemExit(f"Missing translation: {jpath}")
        strings = json.loads(jpath.read_text(encoding="utf-8"))
        blob = write_resources(strings)
        (OUT_RES / res_name).write_bytes(blob)
        print(f"{res_name}: {len(strings)} strings, {len(blob)} bytes")
        resources.append((res_name, blob))

    # Compare size vs ja
    pe = dnfile.dnPE(str(JA_DLL))
    print(f"JA ResourcesSize={pe.net.struct.ResourcesSize}")
    total = sum(4 + len(b) for _, b in resources) + 16  # padding slack
    print(f"Approx new size={total}")

    patch_satellite(JA_DLL, KO_DLL, resources)


if __name__ == "__main__":
    main()
