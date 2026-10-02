import json
import tempfile
import unittest
from pathlib import Path
import lens
import cli


class LensParseTest(unittest.TestCase):
    def test_health_line_parsed(self):
        text = "VPS uptime 5 weeks, RAM used 1.1Gi, load averages 0.20 0.15 0.10 did:key:z6MkAbC1234567890 task id 42"
        rec = lens.parse_one(14270808, text)
        self.assertEqual(rec["kind"], "telemetry")
        self.assertTrue(rec["did"].startswith("did:key:"))
        self.assertTrue(rec["did_valid"])
        self.assertIsNotNone(rec["ram_mib"])
        self.assertAlmostEqual(rec["ram_mib"], 1126.4, places=1)
        self.assertEqual(rec["load1"], 0.20)
        self.assertEqual(rec["task_id"], "42")
        self.assertIsNotNone(rec["uptime_days"])

    def test_noise_split(self):
        self.assertEqual(lens.classify_line("heartbeat online"), "noise")
        self.assertEqual(lens.classify_line("DID active confirmation"), "noise")
        self.assertEqual(lens.classify_line("continuous participation"), "noise")
        text = "uptime 2 days RAM 800Mi load averages 0.1 0.1 0.1"
        self.assertEqual(lens.classify_line(text), "telemetry")

    def test_did_shape(self):
        ok, _ = lens.did_ok("did:key:z6MkAbC1234567890")
        self.assertTrue(ok)
        ok2, _ = lens.did_ok("did:key:bad chars!!")
        self.assertFalse(ok2)
        ok3, _ = lens.did_ok("")
        self.assertFalse(ok3)

    def test_grade_limits(self):
        rec = lens.parse_one(1, "uptime 1 day RAM used 2100Mi load averages 0.1 0.1 0.1 did:key:z6MkAbC1234567890")
        limits = dict(lens.DEFAULT_LIMITS)
        self.assertEqual(lens.grade_one(rec, limits), "fail")
        rec2 = lens.parse_one(2, "uptime 1 day RAM used 1600Mi load averages 0.1 0.1 0.1 did:key:z6MkAbC1234567890")
        self.assertEqual(lens.grade_one(rec2, limits), "warn")
        rec3 = lens.parse_one(3, "uptime 1 day RAM used 500Mi load averages 0.1 0.1 0.1 did:key:z6MkAbC1234567890")
        self.assertEqual(lens.grade_one(rec3, limits), "pass")

    def test_summary_sorted_and_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "in.txt"
            line_a = json.dumps({"seq": 20, "room": "technocore", "text": "heartbeat online"})
            line_b = json.dumps({"seq": 10, "room": "technocore", "text": "VPS uptime 5 weeks RAM used 1.1Gi load averages 0.2 0.1 0.1 did:key:z6MkAbC1234567890"})
            p.write_text(line_a + "\n" + line_b + "\n", encoding="utf-8")
            content = p.read_text(encoding="utf-8")
            records = lens.parse_input_text(content)
            summary = lens.summarize_records(records)
            seqs = [r["seq"] for r in summary["records"]]
            self.assertEqual(seqs, [10, 20])
            self.assertEqual(len(summary["checksum"]), 64)
            out_json = Path(tmp) / "out.json"
            out_json.write_text(lens.summary_to_json(summary), encoding="utf-8")
            back = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(back["checksum"], summary["checksum"])
            md = lens.summary_to_markdown(summary)
            self.assertIn("overall:", md)
            self.assertIn("| seq", md)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "in.txt"
            p.write_text("VPS uptime 5 weeks RAM used 500Mi load averages 0.1 0.1 0.1 did:key:z6MkAbC1234567890\n", encoding="utf-8")
            out = Path(tmp) / "o.json"
            code = cli.main(["--input", str(p), "--json", str(out)])
            self.assertEqual(code, 0)
            p.write_text("VPS uptime 5 weeks RAM used 1600Mi load averages 0.1 0.1 0.1 did:key:z6MkAbC1234567890\n", encoding="utf-8")
            code2 = cli.main(["--input", str(p), "--json", str(out)])
            self.assertEqual(code2, 1)
            p.write_text("VPS uptime 5 weeks RAM used 3000Mi load averages 0.1 0.1 0.1 did:key:z6MkAbC1234567890\n", encoding="utf-8")
            code3 = cli.main(["--input", str(p), "--json", str(out)])
            self.assertEqual(code3, 2)


if __name__ == "__main__":
    unittest.main()
