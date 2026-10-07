#!/usr/bin/env python3
"""Extract .resources blobs from Devolutions.Resources assemblies."""
import json
import struct
import sys
from pathlib import Path

import dnfile


def get_resources_file_offset(pe: dnfile.dnPE) -> int:
    resources_rva = pe.net.struct.ResourcesRva
    return pe.get_offset_from_rva(resources_rva)


def extract_all(path: str, outdir: str) -> list[dict]:
    pe = dnfile.dnPE(path)
    file_off = get_resources_file_offset(pe)
    raw = pe.__data__
    Path(outdir).mkdir(parents=True, exist_ok=True)
    rows = list(pe.net.mdtables.ManifestResource)
    rows = sorted(
        rows,
        key=lambda r: int(r.Offset.value if hasattr(r.Offset, "value") else r.Offset),
    )
    results = []
    for row in rows:
        name = str(row.Name)
        off = int(row.Offset.value if hasattr(row.Offset, "value") else row.Offset)
        abs_off = file_off + off
        length = struct.unpack_from("<I", raw, abs_off)[0]
        blob = raw[abs_off + 4 : abs_off + 4 + length]
        safe = name.replace("/", "_")
        out = Path(outdir) / safe
        out.write_bytes(blob)
        info = {"name": name, "offset": off, "length": length, "file": str(out)}
        results.append(info)
        print(f"{name}: offset={off} len={length} -> {out}")
    return results


# Minimal .resources reader (ResourceManager binary format)
# Format: ResourceSet magic, version, num resources, then hashes/names/data


def read7bit(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, pos


def read_resources(blob: bytes) -> dict[str, object]:
    """Parse .NET ResourceReader binary format into a dict of string values only."""
    pos = 0
    magic = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    if magic != 0xBEEFCACE:
        raise ValueError(f"Bad magic: {hex(magic)}")
    header_ver = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    header_size = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    # skip reader type names
    reader_type_len, pos = read7bit(blob, pos)
    pos += reader_type_len
    set_type_len, pos = read7bit(blob, pos)
    pos += set_type_len
    # pad to 8-byte alignment from start? Actually pad after types to align to 8
    # The header_size includes everything from after header_size field through padding
    # Recalculate: after magic+ver+headerSize we consumed header_size bytes of header
    # Simpler approach: pos after reading types, then align
    # Standard: start of version/num is at 4+4+4+header_size
    pos = 4 + 4 + 4 + header_size
    version = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    num_resources = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    num_types = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    types = []
    for _ in range(num_types):
        tlen, pos = read7bit(blob, pos)
        types.append(blob[pos : pos + tlen].decode("utf-8", errors="replace"))
        pos += tlen
    # 8-byte align
    pad = (8 - (pos % 8)) % 8
    pos += pad
    # name hashes
    pos += 4 * num_resources
    # name positions
    name_positions = [
        struct.unpack_from("<I", blob, pos + 4 * i)[0] for i in range(num_resources)
    ]
    pos += 4 * num_resources
    data_section_offset = struct.unpack_from("<I", blob, pos)[0]
    pos += 4
    name_section_start = pos
    data_section_start = data_section_offset  # absolute from start of blob

    result = {}
    for i in range(num_resources):
        np = name_section_start + name_positions[i]
        name_byte_len, np = read7bit(blob, np)
        # name is UTF-16LE
        name = blob[np : np + name_byte_len].decode("utf-16-le")
        np += name_byte_len
        data_offset = struct.unpack_from("<I", blob, np)[0]
        dp = data_section_start + data_offset
        type_index, dp = read7bit(blob, dp)
        # type_index 0 = null, 1 = string (for ResourceTypeCode in v2)
        # In runtime ResourceTypeCode:
        # Null=0, String=1, Boolean=2, ... ByteArray=32, Stream=33, StartOfUserTypes=64
        if type_index == 1:  # String
            slen, dp = read7bit(blob, dp)
            value = blob[dp : dp + slen].decode("utf-8")
            result[name] = value
        elif type_index == 0:
            result[name] = None
        else:
            # non-string: store marker
            result[name] = {"__type": type_index, "__typestr": types[type_index - 64] if type_index >= 64 and type_index - 64 < len(types) else None}
    return result


def dump_strings(resources_path: Path, json_path: Path) -> int:
    blob = resources_path.read_bytes()
    try:
        data = read_resources(blob)
    except Exception as e:
        print(f"FAIL parse {resources_path}: {e}")
        return 0
    strings = {k: v for k, v in data.items() if isinstance(v, str)}
    json_path.write_text(
        json.dumps(strings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{resources_path.name}: {len(strings)} strings -> {json_path}")
    return len(strings)


def main():
    root = Path(__file__).resolve().parent
    extract_all(str(root / "Devolutions.Resources.dll"), str(root / "_extract" / "en"))
    extract_all(
        str(root / "ja" / "Devolutions.Resources.resources.dll"),
        str(root / "_extract" / "ja"),
    )
    for culture_dir in (root / "_extract").iterdir():
        if not culture_dir.is_dir():
            continue
        for f in culture_dir.glob("*.resources"):
            dump_strings(f, f.with_suffix(".json"))


if __name__ == "__main__":
    main()
