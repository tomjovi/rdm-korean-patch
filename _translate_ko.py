#!/usr/bin/env python3
"""Fast EN->KO batch translation with Bing + local cache."""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import translators as ts

ROOT = Path(__file__).resolve().parent
EXTRACT = ROOT / "_extract"
CACHE_PATH = EXTRACT / "ko_cache.json"
OUT_DIR = EXTRACT / "ko"
SEP = "\n<|>\n"

PLACEHOLDER_RE = re.compile(
    r"(\{\{[^}]+\}\}|\{[0-9]+(?::[^}]*)?\}|%[sdif]|\\[rnt])"
)


def protect(text: str) -> tuple[str, list[str]]:
    tokens: list[str] = []

    def repl(m: re.Match) -> str:
        tokens.append(m.group(0))
        return "[[" + str(len(tokens) - 1) + "]]"

    return PLACEHOLDER_RE.sub(repl, text), tokens


def restore(text: str, tokens: list[str]) -> str:
    for i, tok in enumerate(tokens):
        text = text.replace("[[" + str(i) + "]]", tok)
        text = text.replace("[" + str(i) + "]", tok)
    return text


def should_skip(value: str) -> bool:
    v = value.strip()
    if not v or len(v) <= 1:
        return True
    letters = sum(1 for c in v if c.isalpha())
    if letters == 0:
        return True
    hangul = sum(1 for c in v if "\uac00" <= c <= "\ud7a3")
    if hangul >= max(1, letters // 2):
        return True
    if " " not in v and v.isascii() and (
        v.isupper() or re.fullmatch(r"[A-Za-z0-9._+\-]+", v)
    ):
        if len(v) < 48 and not v.endswith("."):
            return True
    return False


def load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def translate_one(text: str, engine: str = "bing") -> str:
    protected, tokens = protect(text)
    for attempt in range(6):
        try:
            out = ts.translate_text(
                protected,
                translator=engine,
                from_language="en",
                to_language="ko",
            )
            if not out:
                return text
            return restore(out, tokens)
        except Exception as e:
            time.sleep(1.2 * (attempt + 1))
            if attempt == 3:
                engine = "google" if engine == "bing" else "bing"
            if attempt == 5:
                print(f"FAIL: {e!r} :: {text[:60]!r}", flush=True)
                return text
    return text


def translate_batch_joined(texts: list[str], engine: str = "bing") -> list[str]:
    if len(texts) == 1:
        return [translate_one(texts[0], engine)]
    protected_list = []
    tokens_list = []
    for t in texts:
        p, tok = protect(t)
        protected_list.append(p)
        tokens_list.append(tok)
    blob = SEP.join(protected_list)
    for attempt in range(6):
        try:
            out = ts.translate_text(
                blob,
                translator=engine,
                from_language="en",
                to_language="ko",
            )
            parts = out.split(SEP)
            if len(parts) != len(texts):
                parts = re.split(r"\n(?:<\|>)?\n", out)
            if len(parts) != len(texts):
                raise ValueError(f"split mismatch {len(parts)}!={len(texts)}")
            return [restore(p.strip(), tok) for p, tok in zip(parts, tokens_list)]
        except Exception:
            time.sleep(1.0 * (attempt + 1))
            if attempt >= 2:
                return [translate_one(t, engine) for t in texts]
    return texts


def translate_values(
    values: list[str], cache: dict[str, str], workers: int = 12
) -> list[str]:
    result: list[str | None] = [None] * len(values)
    todo_indices: list[int] = []

    for i, v in enumerate(values):
        if v in cache:
            result[i] = cache[v]
        elif should_skip(v):
            cache[v] = v
            result[i] = v
        else:
            todo_indices.append(i)

    print(
        f"  cached/skip={len(values) - len(todo_indices)} todo={len(todo_indices)}",
        flush=True,
    )

    batches: list[list[int]] = []
    singles: list[int] = []
    cur: list[int] = []
    cur_len = 0
    for i in todo_indices:
        v = values[i]
        if "\n" in v or "\r" in v or len(v) > 180:
            if cur:
                batches.append(cur)
                cur, cur_len = [], 0
            singles.append(i)
        else:
            cur.append(i)
            cur_len += len(v)
            if len(cur) >= 16 or cur_len > 1000:
                batches.append(cur)
                cur, cur_len = [], 0
    if cur:
        batches.append(cur)

    done = 0
    total = len(todo_indices)

    def work_batch(idxs: list[int]) -> tuple[list[int], list[str]]:
        texts = [values[i] for i in idxs]
        outs = translate_batch_joined(texts)
        return idxs, outs

    def work_single(idx: int) -> tuple[list[int], list[str]]:
        return [idx], [translate_one(values[idx])]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work_batch, b) for b in batches]
        futs += [ex.submit(work_single, s) for s in singles]
        for fut in as_completed(futs):
            idxs, outs = fut.result()
            for i, o in zip(idxs, outs):
                cache[values[i]] = o
                result[i] = o
            done += len(idxs)
            if done % 200 < len(idxs) or done == total:
                save_cache(cache)
                print(f"  progress {done}/{total} cache={len(cache)}", flush=True)

    save_cache(cache)
    return [r if r is not None else values[i] for i, r in enumerate(result)]


def translate_file(
    en_json: Path, out_json: Path, cache: dict[str, str]
) -> None:
    data = json.loads(en_json.read_text(encoding="utf-8"))
    keys = list(data.keys())
    values = [data[k] for k in keys]
    print(f"=== {en_json.name}: {len(values)} ===", flush=True)
    translated = translate_values(values, cache)
    result = dict(zip(keys, translated))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {out_json}", flush=True)


def main():
    cache = load_cache()
    print(f"Cache: {len(cache)}", flush=True)
    mapping = [
        (
            "Devolutions.Resources.Properties.LogResources.json",
            "LogResources.ko.json",
        ),
        (
            "Devolutions.Resources.Properties.MsgResources.json",
            "MsgResources.ko.json",
        ),
        (
            "Devolutions.Resources.Properties.UIResources.json",
            "UIResources.ko.json",
        ),
    ]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for src_name, dst_name in mapping:
        if only and only not in src_name:
            continue
        src = EXTRACT / "en" / src_name
        dst = OUT_DIR / dst_name
        if dst.exists() and "--force" not in sys.argv:
            existing = json.loads(dst.read_text(encoding="utf-8"))
            en = json.loads(src.read_text(encoding="utf-8"))
            if len(existing) == len(en):
                print(f"Skip complete {dst.name}", flush=True)
                continue
        translate_file(src, dst, cache)
    save_cache(cache)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
