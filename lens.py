"""Offline lens for public Technocore VPS health lines."""
import re
import json
import hashlib

DEFAULT_LIMITS = {
    "ram_mib_warn": 1500.0,
    "ram_mib_fail": 2048.0,
    "load1_warn": 1.0,
    "load1_fail": 2.0,
    "load5_warn": 1.0,
    "load5_fail": 2.0,
    "load15_warn": 1.0,
    "load15_fail": 2.0,
}

NOISE_WORDS = [
    "heartbeat",
    "online",
    "did-active",
    "did active",
    "presence",
    "continuous participation",
    "still here",
    "alive",
    "confirmation",
]


def ram_to_mib(amount, unit):
    u = unit.lower()
    if u in ("mib", "mb", "mi", "m"):
        if u == "mb":
            return amount * 1000.0 / 1024.0
        return amount
    if u in ("gib", "gb", "gi", "g"):
        if u == "gb":
            return amount * 1000.0
        return amount * 1024.0
    return amount


def has_telemetry(text):
    low = text.lower()
    pat_load = r"load(?:\s*averages?)?\s*[:=]?\s*\d+(?:\.\d+)?\s*[,/\s]+\s*\d+(?:\.\d+)?\s*[,/\s]+\s*\d+(?:\.\d+)?"
    has_load = re.search(pat_load, low) is not None
    has_ram_word = ("ram" in low or "memory" in low or "mem " in low)
    has_ram_unit = re.search(r"\d+(?:\.\d+)?\s*(gib|mib|gb|mb|gi|mi)\b", low) is not None
    has_ram = has_ram_word and has_ram_unit
    return bool(has_load or has_ram)


def classify_line(text):
    if has_telemetry(text):
        return "telemetry"
    low = text.lower()
    for w in NOISE_WORDS:
        if w in low:
            return "noise"
    return "other"


def did_ok(did):
    if not did:
        return (False, "missing")
    if not did.startswith("did:key:z"):
        return (False, "must start with did:key:z")
    body = did[len("did:key:z"):]
    if len(body) < 10:
        return (False, "too short")
    if re.search(r"^[A-Za-z0-9]+$", body) is None:
        return (False, "bad chars")
    return (True, "ok")


def parse_one(seq, text, room="technocore"):
    kind = classify_line(text)
    did = ""
    m = re.search(r"did:key:[A-Za-z0-9]+", text)
    if m is not None:
        did = m.group(0)
    valid, reason = did_ok(did)
    ram_mib = None
    ram_raw = ""
    low = text.lower()
    if "ram" in low or "memory" in low or "mem " in low:
        rm = re.search(r"(\d+(?:\.\d+)?)\s*(gib|mib|gb|mb|gi|mi|g|m)\b", text, re.IGNORECASE)
        if rm is not None:
            ram_raw = rm.group(0)
            try:
                amount = float(rm.group(1))
            except ValueError:
                amount = 0.0
            ram_mib = ram_to_mib(amount, rm.group(2))
    load1 = None
    load5 = None
    load15 = None
    lm = re.search(r"load(?:\s*averages?)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*[,/\s]+\s*(\d+(?:\.\d+)?)\s*[,/\s]+\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if lm is not None:
        load1 = float(lm.group(1))
        load5 = float(lm.group(2))
        load15 = float(lm.group(3))
    uptime_raw = ""
    uptime_days = None
    um = re.search(r"uptime\s*[:=]\s*([^,;\n|]+)", text, re.IGNORECASE)
    if um is not None:
        uptime_raw = um.group(1).strip()
    else:
        wm = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*weeks?\b", text, re.IGNORECASE)
        if wm is not None:
            uptime_raw = wm.group(0).strip()
    if uptime_raw == "":
        if re.search(r"\buptime\b", text, re.IGNORECASE) is not None:
            uptime_raw = "uptime noted"
    if uptime_raw != "":
        uptime_days = uptime_to_days(text, uptime_raw)
    task_id = ""
    tm = re.search(r"task\s*(?:id)?\s*[:#=]?\s*(\d+)", text, re.IGNORECASE)
    if tm is not None:
        task_id = tm.group(1)
    missing = []
    if uptime_raw == "":
        missing.append("uptime")
    if ram_mib is None:
        missing.append("ram")
    if load1 is None:
        missing.append("load")
    if did == "":
        missing.append("did")
    rec = {
        "seq": int(seq),
        "room": str(room),
        "text": str(text),
        "kind": kind,
        "uptime_raw": uptime_raw,
        "uptime_days": uptime_days,
        "ram_raw": ram_raw,
        "ram_mib": ram_mib,
        "load1": load1,
        "load5": load5,
        "load15": load15,
        "did": did,
        "did_valid": bool(valid),
        "did_reason": reason,
        "task_id": task_id,
        "missing": missing,
    }
    return rec


def uptime_to_days(full_text, uptime_raw):
    total = 0.0
    found = False
    wm = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*weeks?\b", full_text, re.IGNORECASE)
    if wm is not None:
        total = total + float(wm.group(1)) * 7.0
        found = True
    dm = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*days?\b", full_text, re.IGNORECASE)
    if dm is not None:
        total = total + float(dm.group(1))
        found = True
    hm = re.search(r"(\d+(?:\.\d+)?)\s*-?\s*hours?\b", full_text, re.IGNORECASE)
    if hm is not None:
        total = total + float(hm.group(1)) / 24.0
        found = True
    if found:
        return round(total, 4)
    if uptime_raw != "":
        return None
    return None


def grade_one(rec, limits):
    if rec.get("ram_mib") is None and rec.get("load1") is None:
        return "unknown"
    status = "pass"
    ram = rec.get("ram_mib")
    if ram is not None:
        if ram >= float(limits["ram_mib_fail"]):
            return "fail"
        if ram >= float(limits["ram_mib_warn"]):
            status = "warn"
    for key in ("load1", "load5", "load15"):
        val = rec.get(key)
        if val is None:
            continue
        short = key.replace("load", "load")
        wkey = short + "_warn"
        fkey = short + "_fail"
        if wkey not in limits:
            continue
        if float(val) >= float(limits[fkey]):
            return "fail"
        if float(val) >= float(limits[wkey]):
            status = "warn"
    return status


def parse_input_text(content):
    records = []
    lines = content.splitlines()
    auto_seq = 1
    for line in lines:
        s = line.strip()
        if s == "":
            continue
        seq = None
        room = "technocore"
        text = s
        if s.startswith("{"):
            try:
                obj = json.loads(s)
            except ValueError:
                obj = None
            if isinstance(obj, dict):
                if "text" in obj:
                    text = str(obj.get("text", ""))
                    room = str(obj.get("room", "technocore"))
                    try:
                        seq = int(obj.get("seq", auto_seq))
                    except (ValueError, TypeError):
                        seq = auto_seq
                else:
                    seq = auto_seq
                    text = s
            else:
                seq = auto_seq
                text = s
        else:
            seq = auto_seq
            text = s
        rec = parse_one(seq, text, room)
        records.append(rec)
        auto_seq = auto_seq + 1
        if seq is not None and seq >= auto_seq:
            auto_seq = seq + 1
    return records


def checksum_records(sorted_recs):
    parts = []
    for r in sorted_recs:
        parts.append(str(r["seq"]) + ":" + str(r["text"]))
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def summarize_records(records, limits=None):
    if limits is None:
        limits = dict(DEFAULT_LIMITS)
    ordered = sorted(records, key=lambda r: int(r["seq"]))
    graded = []
    counts = {"telemetry": 0, "noise": 0, "other": 0, "pass": 0, "warn": 0, "fail": 0, "unknown": 0}
    for r in ordered:
        grade = "unknown"
        if r["kind"] == "telemetry":
            grade = grade_one(r, limits)
        else:
            grade = "unknown"
        item = dict(r)
        item["grade"] = grade
        graded.append(item)
        if r["kind"] in counts:
            counts[r["kind"]] = counts[r["kind"]] + 1
        if grade in counts:
            counts[grade] = counts[grade] + 1
    overall = "pass"
    if counts["fail"] > 0:
        overall = "fail"
    elif counts["warn"] > 0:
        overall = "warn"
    checksum = checksum_records(ordered)
    summary = {
        "counts": counts,
        "limits": limits,
        "overall": overall,
        "checksum": checksum,
        "records": graded,
    }
    return summary


def summary_to_json(summary):
    return json.dumps(summary, sort_keys=True, indent=2)


def summary_to_markdown(summary):
    lines = []
    lines.append("# VPS health summary")
    lines.append("")
    lines.append("overall: " + str(summary["overall"]))
    lines.append("checksum: " + str(summary["checksum"]))
    lines.append("")
    counts = summary["counts"]
    cl = "counts telemetry=" + str(counts["telemetry"])
    cl = cl + " noise=" + str(counts["noise"])
    cl = cl + " other=" + str(counts["other"])
    lines.append(cl)
    gl = "grades pass=" + str(counts["pass"])
    gl = gl + " warn=" + str(counts["warn"])
    gl = gl + " fail=" + str(counts["fail"])
    gl = gl + " unknown=" + str(counts["unknown"])
    lines.append(gl)
    lines.append("")
    lines.append("| seq | did | uptime | ram | load 1/5/15 | grade |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in summary["records"]:
        did = r["did"]
        if len(did) > 18:
            did = did[0:18] + ".."
        if did == "":
            did = "-"
        up = r["uptime_raw"]
        if up == "":
            up = "-"
        ram = r["ram_raw"]
        if ram == "":
            ram = "-"
        if r["load1"] is None:
            load = "-"
        else:
            load = str(r["load1"]) + " " + str(r["load5"]) + " " + str(r["load15"])
        row = "| " + str(r["seq"]) + " | " + did + " | " + up + " | " + ram + " | " + load + " | " + str(r["grade"]) + " |"
        lines.append(row)
    lines.append("")
    return "\n".join(lines)
