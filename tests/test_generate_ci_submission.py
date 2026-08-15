import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "generate-ci-submission.py"


def run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, cwd=cwd, env=env, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )


class GenerateCiSubmissionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        run("git", "init", "-b", "main", cwd=self.root)
        run("git", "config", "user.name", "Test Learner", cwd=self.root)
        run("git", "config", "user.email", "learner@example.com", cwd=self.root)
        run("git", "remote", "add", "origin", "https://github.com/test-learner/lab6-actions-test.git", cwd=self.root)
        self._write(
            ".github/workflows/ci.yml",
            """
            name: CI
            on: [pull_request]
            permissions:
              contents: read
            jobs:
              test:
                runs-on: ubuntu-latest
                steps:
                  - uses: actions/checkout@v4
                  - name: Run tests with coverage
                    run: python -m pytest -q --cov=prediction_pipeline_demo --cov-fail-under=70
                  - name: Run demo pipeline
                    run: python prediction_pipeline_demo.py
              optional_comparison:
                runs-on: self-hosted
                steps:
                  - run: python3 --version
            """,
        )
        self._write("prediction_pipeline_demo.py", 'print("Trained model score is: -0.08125")\n')
        self._write("tests/test_demo.py", "def test_demo():\n    assert True\n")
        run("git", "add", ".", cwd=self.root)
        run("git", "commit", "-m", "complete CI lab", cwd=self.root)
        self.evidence = self.root / "evidence"
        self.evidence.mkdir()
        self.failed_log = self.evidence / "failed-run.txt"
        self.successful_log = self.evidence / "successful-run.txt"
        self.failed_log.write_text(
            "tests passed\nFAIL Required test coverage of 70% not reached. Total coverage: 62.50%\n",
            encoding="utf-8",
        )
        self.successful_log.write_text(
            "Required test coverage of 70% reached. Total coverage: 87.50%\n"
            "Trained model score is: -0.08125\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

    def generate(self, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return run(
            "python3", str(SCRIPT),
            "--learner", "Test Learner",
            "--repository-url", "https://github.com/test-learner/lab6-actions-test",
            "--pr-url", "https://github.com/test-learner/lab6-actions-test/pull/3",
            "--failed-run-url", "https://github.com/test-learner/lab6-actions-test/actions/runs/1001",
            "--failed-log", str(self.failed_log),
            "--successful-run-url", "https://github.com/test-learner/lab6-actions-test/actions/runs/1002",
            "--successful-log", str(self.successful_log),
            cwd=self.root, env=env,
        )

    def manifest(self) -> dict:
        return json.loads((self.root / "submission" / "ci-manifest.json").read_text(encoding="utf-8"))

    def test_generates_complete_matching_report_without_github_or_actions(self) -> None:
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        marker = self.root / "gh-was-called"
        fake_gh = fake_bin / "gh"
        fake_gh.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 99\n", encoding="utf-8")
        fake_gh.chmod(0o755)
        env = dict(os.environ)
        env["PATH"] = f"{fake_bin}:{env['PATH']}"

        result = self.generate(env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        manifest = self.manifest()
        report = (self.root / "submission" / "ci-report.html").read_text(encoding="utf-8")
        self.assertTrue(manifest["complete"])
        self.assertTrue(all(item["status"] == "present" for item in manifest["checks"]))
        self.assertEqual(manifest["identifiers"]["coverage_threshold"], 70.0)
        self.assertEqual(manifest["identifiers"]["model_score"], "-0.08125")
        self.assertIn("Total coverage: 62.50%", report)
        self.assertIn("Total coverage: 87.50%", report)
        self.assertEqual(manifest["manual_spot_checks"], ["quality_gate", "ci_design"])

    def test_marks_dirty_workflow_and_inconsistent_run_evidence_missing(self) -> None:
        workflow = self.root / ".github/workflows/ci.yml"
        workflow.write_text(workflow.read_text(encoding="utf-8") + "\n# uncommitted\n", encoding="utf-8")
        self.successful_log.write_text(
            "Required test coverage of 75% reached. Total coverage: 88.00%\n",
            encoding="utf-8",
        )

        result = self.generate()

        self.assertEqual(result.returncode, 1)
        statuses = {item["name"]: item["status"] for item in self.manifest()["checks"]}
        self.assertEqual(statuses["immutable_repository_revision"], "missing")
        self.assertEqual(statuses["successful_coverage_evidence"], "missing")
        self.assertEqual(statuses["successful_pipeline_score"], "missing")

    def test_checks_runner_threshold_pipeline_and_secret_dependency_statically(self) -> None:
        workflow = self.root / ".github/workflows/ci.yml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8")
            .replace("ubuntu-latest", "self-hosted")
            .replace("--cov-fail-under=70", "--cov-fail-under=60")
            .replace("run: python prediction_pipeline_demo.py", "env:\n          TOKEN: ${{ secrets.COURSE_TOKEN }}"),
            encoding="utf-8",
        )
        run("git", "commit", "-am", "misconfigure workflow", cwd=self.root)

        result = self.generate()

        self.assertEqual(result.returncode, 1)
        statuses = {item["name"]: item["status"] for item in self.manifest()["checks"]}
        self.assertEqual(statuses["github_hosted_runner"], "missing")
        self.assertEqual(statuses["coverage_threshold"], "missing")
        self.assertEqual(statuses["no_secret_dependencies"], "missing")
        self.assertEqual(statuses["lightweight_pipeline_step"], "missing")

    def test_withholds_plaintext_credentials_from_both_outputs(self) -> None:
        secret = "ghp_abcdefghijklmnopqrstuvwxyz123456"
        self.successful_log.write_text(
            self.successful_log.read_text(encoding="utf-8").replace(
                "Total coverage: 87.50%", f"Total coverage: 87.50% api_key={secret}"
            ),
            encoding="utf-8",
        )

        result = self.generate()

        self.assertEqual(result.returncode, 1)
        combined = (
            (self.root / "submission" / "ci-report.html").read_text(encoding="utf-8")
            + (self.root / "submission" / "ci-manifest.json").read_text(encoding="utf-8")
        )
        self.assertNotIn(secret, combined)
        self.assertIn("Content withheld", combined)

    def test_rejects_missing_evidence_without_creating_outputs(self) -> None:
        self.failed_log.unlink()

        result = self.generate()

        self.assertEqual(result.returncode, 2)
        self.assertIn("Missing required saved evidence", result.stderr)
        self.assertFalse((self.root / "submission").exists())


if __name__ == "__main__":
    unittest.main()
