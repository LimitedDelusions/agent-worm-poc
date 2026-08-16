from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib, json, re, time

_JSON_OBJECT = re.compile(r"\{(?:[^{}]|(?R))*\}") if False else None

def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_json(path: str | Path, value: Any) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")

def append_jsonl(path: str | Path, value: Any) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(value, ensure_ascii=False) + "\n")

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: str | Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def stable_int(*parts: object, modulo: int = 2_000_000_000) -> int:
    raw="|".join(str(p) for p in parts).encode()
    return int(hashlib.sha256(raw).hexdigest()[:16], 16) % modulo

def stable_token(prefix: str, *parts: object, length: int = 12) -> str:
    raw="|".join(str(p) for p in parts).encode()
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:length].upper()}"

def extract_json_object(text: str) -> dict[str, Any]:
    text=text.strip()
    if text.startswith("```"):
        text=re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text=re.sub(r"\s*```$", "", text)
    try:
        obj=json.loads(text)
        if isinstance(obj, dict): return obj
    except Exception:
        pass
    starts=[i for i,c in enumerate(text) if c=="{"]
    for start in starts:
        depth=0; in_string=False; escape=False
        for i in range(start, len(text)):
            c=text[i]
            if in_string:
                if escape: escape=False
                elif c=="\\": escape=True
                elif c=='"': in_string=False
                continue
            if c=='"': in_string=True
            elif c=="{": depth+=1
            elif c=="}":
                depth-=1
                if depth==0:
                    candidate=text[start:i+1]
                    try:
                        obj=json.loads(candidate)
                        if isinstance(obj, dict): return obj
                    except Exception:
                        break
    raise ValueError("No valid JSON object found in model response")

def utc_stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

def ensure_no_secret_text(root: Path) -> list[str]:
    findings=[]
    token_re=re.compile(r"\bhf_[A-Za-z0-9]{20,}\b|\bghp_[A-Za-z0-9]{20,}\b")
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".py",".md",".json",".yml",".yaml",".sh",".toml",".txt"}:
            try: text=p.read_text(encoding="utf-8")
            except Exception: continue
            if token_re.search(text): findings.append(str(p.relative_to(root)))
    return findings
