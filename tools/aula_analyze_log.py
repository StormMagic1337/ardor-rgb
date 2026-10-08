"""Decodes a hid.dll log of the AULA vendor app (tools/aula_hidlog): groups report-6 transfers by
command and prints the bytes that changed at each step.
  python tools/aula_analyze_log.py hid_log.txt"""
import re, sys
from collections import Counter

step, last, seen = "start", {}, Counter()
for line in open(sys.argv[1], encoding="utf-8-sig"):
    if line.startswith("==="):
        step = line.strip("= \r\n")
        print(f"\n## {step}")
        continue
    m = re.match(r"(\S+) (SetFeature|GetFeature)\s+(\S+ \S+ \S+)\s+(ok|ERR)\s+len=(\d+)\s+(?:req=\w+ )?(.*)", line)
    if not m:
        continue
    t, op, tag, ok, n, hx = m.groups()
    b = bytes.fromhex(hx)
    cmd, length = b[1], b[6] | b[7] << 8
    data = b[8:8 + length] if length else b""
    key = (op, cmd)
    seen[key] += 1
    head = f"{t} {op[:3]} cmd={cmd:02x} hdr={b[:8].hex(' ')}"
    if op == "SetFeature" and cmd & 0x80:      # read request: only header matters
        continue
    prev = last.get(key)
    last[key] = data
    if prev is None:
        print(f"{head} FIRST len={length}: {data.hex(' ')}")
    elif prev != data:
        diff = [f"{i}:{prev[i]:02x}->{data[i]:02x}" for i in range(min(len(prev), len(data))) if prev[i] != data[i]]
        print(f"{head} diff({len(diff)}): {' '.join(diff[:40])}{' ...' if len(diff) > 40 else ''}")
print("\n", dict(seen))
