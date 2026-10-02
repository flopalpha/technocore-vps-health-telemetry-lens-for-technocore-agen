"""Command line run for the lens."""
import argparse
import json
import sys
from pathlib import Path
import lens


def build_parser():
    p = argparse.ArgumentParser(
        description="Split health lines from noise and grade RAM and load."
    )
    p.add_argument("--input", required=True, help="Path to input text file.")
    p.add_argument("--json", default="", help="Path to write JSON summary.")
    p.add_argument("--md", default="", help="Path to write Markdown table.")
    p.add_argument("--ram-warn", type=float, default=1500.0)
    p.add_argument("--ram-fail", type=float, default=2048.0)
    p.add_argument("--load-warn", type=float, default=1.0)
    p.add_argument("--load-fail", type=float, default=2.0)
    p.add_argument("--load1-warn", type=float, default=None)
    p.add_argument("--load1-fail", type=float, default=None)
    return p


def make_limits(args):
    load1_warn = args.load1_warn
    if load1_warn is None:
        load1_warn = args.load_warn
    load1_fail = args.load1_fail
    if load1_fail is None:
        load1_fail = args.load_fail
    limits = {
        "ram_mib_warn": float(args.ram_warn),
        "ram_mib_fail": float(args.ram_fail),
        "load1_warn": float(load1_warn),
        "load1_fail": float(load1_fail),
        "load5_warn": float(args.load_warn),
        "load5_fail": float(args.load_fail),
        "load15_warn": float(args.load_warn),
        "load15_fail": float(args.load_fail),
    }
    return limits


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    limits = make_limits(args)
    path = Path(args.input)
    content = path.read_text(encoding="utf-8")
    records = lens.parse_input_text(content)
    summary = lens.summarize_records(records, limits)
    text_json = lens.summary_to_json(summary)
    text_md = lens.summary_to_markdown(summary)
    if args.json:
        Path(args.json).write_text(text_json, encoding="utf-8")
    else:
        sys.stdout.write(text_json + "\n")
    if args.md:
        Path(args.md).write_text(text_md, encoding="utf-8")
    status = summary["overall"]
    if status == "fail":
        return 2
    if status == "warn":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
