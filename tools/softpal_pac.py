#!/usr/bin/env python3
"""Softpal / Amuse Craft PAC v2 (PAC/AMUSE) unpacker, repacker, and $-table codec.

Verified byte-for-byte against all 17 .pac archives of 紅月ゆれる恋あかり (Akatsuki Yureru Koi Akari).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys
from dataclasses import dataclass
from typing import Iterable

PAC2_MAGIC = b"PAC "
PAC2_HEADER_SIZE = 0x804
PAC2_ENTRY_SIZE = 0x28
PAC2_NAME_SIZE = 0x20
PAC2_BUCKETS = 255  # 0x0C + 255 * 8 = 0x804
SOFTPAL_XOR_KEY = 0x084DF873 ^ 0xFF987DEE  # 0xF7D5859D


@dataclass(frozen=True)
class PacEntry:
    name: str
    raw_name: bytes
    size: int
    offset: int


def is_softpal_encrypted(data: bytes) -> bool:
    return len(data) > 16 and data[0] == ord("$")


def decrypt_softpal_table(data: bytes) -> bytes:
    """Decrypt a Softpal '$'-prefixed binary table (TEXT.DAT, POINT.DAT, etc.)."""
    if not is_softpal_encrypted(data):
        return data
    buf = bytearray(data)
    count = (len(buf) - 16) // 4
    shift = 4
    for i in range(count):
        off = 16 + i * 4
        b0 = buf[off]
        s = shift & 7
        buf[off] = ((b0 << s) | (b0 >> (8 - s))) & 0xFF
        shift += 1
        val = struct.unpack_from("<I", buf, off)[0] ^ SOFTPAL_XOR_KEY
        struct.pack_into("<I", buf, off, val)
    return bytes(buf)


def encrypt_softpal_table(data: bytes) -> bytes:
    """Encrypt a Softpal '$'-prefixed binary table (exact inverse of decrypt_softpal_table)."""
    if not is_softpal_encrypted(data):
        return data
    buf = bytearray(data)
    count = (len(buf) - 16) // 4
    shift = 4
    for i in range(count):
        off = 16 + i * 4
        val = struct.unpack_from("<I", buf, off)[0] ^ SOFTPAL_XOR_KEY
        struct.pack_into("<I", buf, off, val)
        b0 = buf[off]
        s = shift & 7
        buf[off] = ((b0 >> s) | (b0 << (8 - s))) & 0xFF
        shift += 1
    return bytes(buf)


def read_pac2_index(path: pathlib.Path) -> list[PacEntry]:
    file_size = path.stat().st_size
    with path.open("rb") as f:
        hdr = f.read(PAC2_HEADER_SIZE)
        if len(hdr) < PAC2_HEADER_SIZE or hdr[:4] != PAC2_MAGIC:
            raise ValueError(f"{path}: invalid PAC v2 header")
        count = struct.unpack_from("<I", hdr, 8)[0]
        if count > 200_000:
            raise ValueError(f"{path}: implausible entry count {count}")
        entries: list[PacEntry] = []
        for _ in range(count):
            rec = f.read(PAC2_ENTRY_SIZE)
            if len(rec) != PAC2_ENTRY_SIZE:
                raise ValueError(f"{path}: truncated index")
            raw_name = rec[:PAC2_NAME_SIZE]
            name = raw_name.split(b"\x00", 1)[0].decode("cp932", errors="strict")
            size, offset = struct.unpack_from("<II", rec, PAC2_NAME_SIZE)
            if offset + size > file_size:
                raise ValueError(f"{path}: entry {name!r} out of bounds ({offset}+{size} > {file_size})")
            entries.append(PacEntry(name=name, raw_name=raw_name, size=size, offset=offset))
    return entries


def read_pac2_member(path: pathlib.Path, member_name: str, *, decrypt: bool = False) -> bytes:
    target = member_name.upper()
    entries = read_pac2_index(path)
    for e in entries:
        if e.name.upper() == target:
            with path.open("rb") as f:
                f.seek(e.offset)
                raw = f.read(e.size)
            return decrypt_softpal_table(raw) if decrypt else raw
    raise KeyError(f"{member_name!r} not found in {path}")


def build_pac2_bytes(members: Iterable[tuple[str, bytes]]) -> bytes:
    """Build a valid PAC v2 archive with exact 255-bucket first-byte lookup table.

    Members are sorted by raw CP932 name bytes (matching original Softpal packer order).
    """
    items: list[tuple[bytes, bytes]] = []
    seen: set[bytes] = set()
    for name, payload in members:
        name_bytes = name.encode("cp932")
        if not name_bytes or len(name_bytes) >= PAC2_NAME_SIZE:
            raise ValueError(f"Invalid PAC2 member name length: {name!r}")
        if name_bytes[0] >= PAC2_BUCKETS:
            raise ValueError(f"First byte >= 255 unsupported in PAC2 bucket table: {name!r}")
        if name_bytes.upper() in seen:
            raise ValueError(f"Duplicate PAC2 member name: {name!r}")
        seen.add(name_bytes.upper())
        items.append((name_bytes, payload))

    # Preserve exact bucket grouping by first byte, sorted lexicographically within each bucket
    items.sort(key=lambda x: x[0])

    count = len(items)
    counts = [0] * PAC2_BUCKETS
    for nb, _ in items:
        counts[nb[0]] += 1

    hdr = bytearray(PAC2_HEADER_SIZE)
    hdr[0:4] = PAC2_MAGIC
    struct.pack_into("<II", hdr, 4, 0, count)
    cum = 0
    for c in range(PAC2_BUCKETS):
        struct.pack_into("<II", hdr, 0x0C + c * 8, cum, counts[c])
        cum += counts[c]

    data_offset = PAC2_HEADER_SIZE + count * PAC2_ENTRY_SIZE
    index_buf = bytearray(count * PAC2_ENTRY_SIZE)
    cur_off = data_offset
    for i, (nb, payload) in enumerate(items):
        rec_off = i * PAC2_ENTRY_SIZE
        index_buf[rec_off : rec_off + len(nb)] = nb
        struct.pack_into("<II", index_buf, rec_off + PAC2_NAME_SIZE, len(payload), cur_off)
        cur_off += len(payload)

    out = bytearray(cur_off + 8)
    out[0:PAC2_HEADER_SIZE] = hdr
    out[PAC2_HEADER_SIZE:data_offset] = index_buf
    cur_off = data_offset
    for _, payload in items:
        out[cur_off : cur_off + len(payload)] = payload
        cur_off += len(payload)
    byte_sum = sum(out[:cur_off]) & 0xFFFFFFFF
    struct.pack_into("<I4s", out, cur_off, byte_sum, b"EOF ")
    return bytes(out)


def repack_pac2_with_overrides(
    base_pac: pathlib.Path,
    overrides: dict[str, bytes],
    output_pac: pathlib.Path,
) -> dict[str, str]:
    """Rebuild a PAC v2 archive replacing/adding members in `overrides` (case-insensitive names)."""
    entries = read_pac2_index(base_pac)
    ov_upper = {k.upper(): (k, v) for k, v in overrides.items()}
    members: list[tuple[str, bytes]] = []
    replaced: set[str] = set()
    with base_pac.open("rb") as f:
        for e in entries:
            key = e.name.upper()
            if key in ov_upper:
                _, payload = ov_upper[key]
                members.append((e.name, payload))
                replaced.add(key)
            else:
                f.seek(e.offset)
                members.append((e.name, f.read(e.size)))
    for key, (orig_name, payload) in ov_upper.items():
        if key not in replaced:
            members.append((orig_name.upper(), payload))

    blob = build_pac2_bytes(members)
    output_pac.parent.mkdir(parents=True, exist_ok=True)
    output_pac.write_bytes(blob)
    return {
        "output": str(output_pac),
        "size": str(len(blob)),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "entries": str(len(members)),
    }


def verify_roundtrip(pac_path: pathlib.Path) -> dict[str, object]:
    orig = pac_path.read_bytes()
    entries = read_pac2_index(pac_path)
    members: list[tuple[str, bytes]] = []
    table_checks = 0
    with pac_path.open("rb") as f:
        for e in entries:
            f.seek(e.offset)
            raw = f.read(e.size)
            if is_softpal_encrypted(raw):
                dec = decrypt_softpal_table(raw)
                reenc = encrypt_softpal_table(dec)
                if reenc != raw:
                    raise AssertionError(f"{pac_path.name}/{e.name}: encrypt(decrypt(raw)) mismatch!")
                table_checks += 1
            members.append((e.name, raw))
    rebuilt = build_pac2_bytes(members)
    exact = rebuilt == orig
    return {
        "file": pac_path.name,
        "entries": len(entries),
        "size": len(orig),
        "encrypted_tables_verified": table_checks,
        "exact_byte_match": exact,
        "orig_sha256": hashlib.sha256(orig).hexdigest(),
        "rebuilt_sha256": hashlib.sha256(rebuilt).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Softpal PAC v2 archive utility")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List entries in a .pac archive")
    p_list.add_argument("pac", type=pathlib.Path)

    p_unp = sub.add_parser("unpack", help="Unpack a .pac archive to a directory")
    p_unp.add_argument("pac", type=pathlib.Path)
    p_unp.add_argument("out_dir", type=pathlib.Path)
    p_unp.add_argument("--decrypt", action="store_true", help="Decrypt $-prefixed binary tables")

    p_ver = sub.add_parser("verify", help="Verify byte-for-byte PAC2 + cipher roundtrip")
    p_ver.add_argument("pacs", nargs="+", type=pathlib.Path)

    args = ap.parse_args(argv)
    if args.cmd == "list":
        for e in read_pac2_index(args.pac):
            print(f"{e.name:32s} {e.size:10d} 0x{e.offset:08x}")
        return 0
    if args.cmd == "unpack":
        args.out_dir.mkdir(parents=True, exist_ok=True)
        entries = read_pac2_index(args.pac)
        with args.pac.open("rb") as f:
            for e in entries:
                f.seek(e.offset)
                raw = f.read(e.size)
                if args.decrypt and is_softpal_encrypted(raw):
                    raw = decrypt_softpal_table(raw)
                (args.out_dir / e.name).write_bytes(raw)
        print(f"Unpacked {len(entries)} entries to {args.out_dir}")
        return 0
    if args.cmd == "verify":
        results = [verify_roundtrip(p) for p in args.pacs]
        print(json.dumps(results, indent=2))
        return 0 if all(r["exact_byte_match"] for r in results) else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
