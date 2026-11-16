"""Offline tests for benchmark application checks and cleanup."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location("bench", Path(__file__).resolve().parents[1] / "benchmark/bench.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkTests(unittest.TestCase):
    def test_retry_number_preserves_setup_on_first_requested_cycle(self):
        argv = ["bench.py", "run", "--tier", "intensive", "--tools", "terraform",
                "--runs", "2", "--start-run", "2"]
        with patch.object(bench.sys, "argv", argv), patch.object(bench, "run_cycle", return_value={}) as cycle, patch.object(bench, "append_csv"), patch.object(bench, "report"):
            bench.main()
        self.assertEqual([call.args[2] for call in cycle.call_args_list], [2, 3])
        self.assertEqual([call.kwargs["skip_setup"] for call in cycle.call_args_list], [False, True])

    def test_cloudformation_empty_changeset_is_successful(self):
        ctx = bench.Ctx("simple", "cloudformation", 1, None, True)
        with patch.object(bench, "sh", return_value=0) as command:
            bench.CloudFormation(ctx).noop_preview()
        self.assertIn("--no-fail-on-empty-changeset", command.call_args.args[1])

    def test_http_checks_pong_content_and_writes_evidence(self):
        ctx = bench.Ctx("simple", "terraform", 1, None, False)
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"<title>Pong | Single Player | By Bocaletto Luca</title>"
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(bench, "LOGS_DIR", Path(folder)), \
                patch.object(bench, "capture", return_value="http://example.test"), \
                patch.object(bench, "urlopen", return_value=response):
            bench.verify_http(ctx)
            evidence = json.loads((Path(folder) / "simple-terraform-run1-http.json").read_text())
            self.assertTrue(evidence["ok"])
            self.assertEqual(evidence["status"], 200)

    def test_https_cloudfront_checks_pong(self):
        ctx = bench.Ctx("intensive", "terraform", 1, None, False)
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"<title>Pong | Single Player | By Bocaletto Luca</title>"
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(bench, "LOGS_DIR", Path(folder)), patch.object(bench, "capture", return_value="https://example.test"), patch.object(bench, "urlopen", return_value=response) as request:
                bench.verify_http(ctx)
            request.assert_called_once_with("https://example.test", timeout=10)
            evidence = json.loads((Path(folder) / "intensive-terraform-run1-http.json").read_text())
            self.assertTrue(evidence["ok"])

    def test_missing_url_fails_http_verification(self):
        ctx = bench.Ctx("medium", "pulumi", 1, None, False)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(bench, "LOGS_DIR", Path(folder)), \
                patch.object(bench, "capture", return_value=""):
            with self.assertRaises(bench.StepFailed):
                bench.verify_http(ctx)

    def test_http_failure_still_destroys_deployment(self):
        adapter = MagicMock()
        for name in ("setup", "preview", "deploy", "noop_preview", "destroy"):
            getattr(adapter, name).return_value = 0
        adapter.resources.return_value = 1
        adapter.state.return_value = ("test", 1)
        with patch.dict(bench.ADAPTERS, {"terraform": lambda ctx: adapter}), \
                patch.object(bench, "aws_account", return_value="test"), \
                patch.object(bench, "verify_http", side_effect=bench.StepFailed("http_verification")):
            row = bench.run_cycle("simple", "terraform", 1, None, False, False, check_http=True)
        self.assertFalse(row["ok"])
        self.assertEqual(row["failed_step"], "http_verification")
        adapter.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
