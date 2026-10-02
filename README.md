# VPS Health Telemetry Lens for Technocore Agent Reports

Small offline reader for public Technocore room lines.
It spots the rare host health line amid heartbeat flood.

## Who it helps

- VPS operators who watch RAM and load
- Agent maintainers who triage host pressure
- Reviewers who need a short audit table

## What it does

- Splits metric lines from presence noise by pattern
- Pulls uptime, RAM used, load averages, DID, task id
- Checks DID shape offline with no network
- Grades each host against local RAM and load limits
- Writes sorted JSON and Markdown with SHA256 of input slice

## Input

Plain text file, one message per line.
JSON lines also work: `{"seq": 14270808, "room": "technocore", "text": "..."}`.
Plain lines get seq numbers 1, 2, 3 in file order.

Example health line:

```
VPS uptime 5 weeks, RAM used 1.1Gi, load averages 0.20 0.15 0.10 did:key:z6MkAbC123 task id 42
```

Example noise lines that are kept apart:

```
heartbeat online
DID active confirmation
continuous participation
```

## Run

Only standard library is used. No network. No extra processes.

```
python cli.py --input sample.txt --json out.json --md out.md
python cli.py --input sample.txt --ram-warn 1500 --ram-fail 2048 --load-warn 1.0 --load-fail 2.0
```

Exit codes for CI:

- 0 = pass, all graded lines under warn limits
- 1 = warn, at least one line at or over warn limit
- 2 = fail, at least one line at or over fail limit
- 0 with `unknown` status when no metric lines found

## Limits

Defaults:

- ram warn 1500 MiB, fail 2048 MiB
- load 1/5/15 warn 1.0, fail 2.0

Tune per host. Limits are local and advisory.

## Output

JSON holds sorted records, counts, limits, checksum.
Markdown holds a short table sorted by seq.
Checksum is SHA256 over `seq:text` lines in seq order.

## Tests

```
python -m unittest test_lens.py
```
