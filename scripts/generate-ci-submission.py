#!/usr/bin/env python3
"""Generate the Lab 6 CI report and manifest from local, saved evidence."""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


REPORT_NAME = "ci-report.html"
MANIFEST_NAME = "ci-manifest.json"
CHECKER_VERSION = "1.0"
WORKFLOW_PATH = ".github/workflows/ci.yml"
SECRET_PATTERNS = (
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"\b(?:ghp|github_pat|sk|xox[baprs])_[A-Za-z0-9_-]{16,}\b"),
)
COVERAGE_LINE = re.compile(
    r"Required test coverage of\s+(?P<threshold>\d+(?:\.\d+)?)%\s+"
    r"(?P<result>reached|not reached)\.\s+Total coverage:\s+"
    r"(?P<total>\d+(?:\.\d+)?)%",
    re.IGNORECASE,
)
SCORE_LINE = re.compile(r"Trained model score is:\s*(?P<score>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)")


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check(name: str, present: bool, location: str, identifier: str, detail: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "present" if present else "missing",
        "location": location,
        "identifier": identifier,
        "detail": detail,
    }


def contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def sanitize_url(value: str) -> str:
    """Strip URL credentials, query strings, and fragments before output."""
    value = value.strip()
    scp_match = re.fullmatch(r"git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?", value)
    if scp_match:
        owner, repository = scp_match.groups()
        return f"https://github.com/{owner}/{repository.removesuffix('.git')}"
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "invalid-url-redacted"
    host = parsed.hostname or ""
    return urlunsplit((parsed.scheme, host, parsed.path, "", "")) or "invalid-url-redacted"


def github_repository(value: str) -> tuple[str, tuple[str, str] | None]:
    safe = sanitize_url(value).removesuffix(".git").rstrip("/")
    try:
        parsed = urlsplit(safe)
    except ValueError:
        return safe, None
    parts = [part for part in parsed.path.split("/") if part]
    valid = (
        parsed.scheme == "https" and parsed.hostname == "github.com"
        and parsed.username is None and parsed.password is None and len(parts) == 2
    )
    return safe, (parts[0], parts[1]) if valid else None


def github_evidence_url(value: str, repository: tuple[str, str] | None, kind: str) -> tuple[str, bool]:
    safe = sanitize_url(value).rstrip("/")
    try:
        parsed = urlsplit(safe)
    except ValueError:
        return safe, False
    parts = [part for part in parsed.path.split("/") if part]
    if repository is None or parsed.scheme != "https" or parsed.hostname != "github.com":
        return safe, False
    prefix_ok = len(parts) >= 2 and tuple(parts[:2]) == repository
    suffix = parts[2:]
    if kind == "pull_request":
        shape_ok = len(suffix) == 2 and suffix[0] == "pull" and suffix[1].isdigit() and int(suffix[1]) > 0
    else:
        shape_ok = len(suffix) == 3 and suffix[:2] == ["actions", "runs"] and suffix[2].isdigit() and int(suffix[2]) > 0
    return safe, prefix_ok and shape_ok


def yaml_mapping_body(text: str, parent_key: str, child_key: str) -> str:
    """Return one simple YAML mapping body without importing a YAML library."""
    lines = text.splitlines()
    parent_index = None
    parent_indent = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)" + re.escape(parent_key) + r"\s*:\s*$", line)
        if match:
            parent_index = index
            parent_indent = len(match.group(1))
            break
    if parent_index is None:
        return ""

    child_index = None
    child_indent = 0
    for index in range(parent_index + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= parent_indent:
            break
        match = re.match(r"^(\s*)" + re.escape(child_key) + r"\s*:\s*$", line)
        if match:
            child_index = index
            child_indent = len(match.group(1))
            break
    if child_index is None:
        return ""

    body: list[str] = []
    for line in lines[child_index + 1:]:
        if line.strip():
            indent = len(line) - len(line.lstrip())
            if indent <= child_indent:
                break
        body.append(line)
    return "\n".join(body)


def workflow_configuration(text: str) -> dict[str, object]:
    active = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    required_job = yaml_mapping_body(active, "jobs", "test")
    runners = re.findall(r"^\s*runs-on\s*:\s*['\"]?([^\s'\"]+)", required_job, re.MULTILINE)
    thresholds = [float(value) for value in re.findall(r"--cov-fail-under(?:=|\s+)(\d+(?:\.\d+)?)", required_job)]
    pipeline = bool(re.search(r"(?:python|python3)\s+(?:\./)?prediction_pipeline_demo\.py\b", required_job))
    secrets_reference = bool(
        re.search(r"\$\{\{\s*secrets(?:\.|\[)", active, re.IGNORECASE)
        or re.search(r"^\s*secrets\s*:\s*inherit\s*$", active, re.IGNORECASE | re.MULTILINE)
    )
    return {
        "runners": runners,
        "thresholds": thresholds,
        "pipeline": pipeline,
        "secrets_reference": secrets_reference,
    }


def matching_line(text: str, pattern: re.Pattern[str]) -> tuple[str, re.Match[str] | None]:
    for line in text.splitlines():
        match = pattern.search(line)
        if match:
            return line.strip(), match
    return "", None


def local_display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return path.name


def evidence_block(title: str, source: str, excerpt: str, withheld: bool = False) -> str:
    shown = "Content withheld because an obvious credential pattern was detected." if withheld else excerpt
    return (
        f'<section><h3>{html.escape(title)}</h3><p>Saved source: <code>{html.escape(source)}</code></p>'
        f'<pre>{html.escape(shown or "Required decisive line not found.")}</pre></section>'
    )


def render_report(
    learner: str,
    generated_at: str,
    repository_url: str,
    commit: str,
    pr_url: str,
    failed_run_url: str,
    successful_run_url: str,
    workflow_url: str,
    workflow_text: str,
    checks: list[dict[str, str]],
    failed_source: str,
    failed_excerpt: str,
    successful_source: str,
    success_coverage_excerpt: str,
    score_excerpt: str,
    withheld: set[str],
) -> str:
    overall = "complete" if all(item["status"] == "present" for item in checks) else "incomplete"
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(item['name'])}</td>"
        f"<td class=\"{item['status']}\">{item['status']}</td>"
        f"<td>{html.escape(item['identifier'])}</td>"
        f"<td>{html.escape(item['detail'])}</td>"
        "</tr>" for item in checks
    )
    success_excerpt = "\n".join(part for part in (success_coverage_excerpt, score_excerpt) if part)
    workflow_shown = (
        "Content withheld because an obvious credential pattern was detected."
        if WORKFLOW_PATH in withheld else workflow_text
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lab 6 CI Submission Report</title>
  <style>
    body {{ color:#17202a; font:16px/1.45 system-ui,sans-serif; margin:2rem auto; max-width:76rem; padding:0 1rem; }}
    h1,h2,h3 {{ color:#102a43; }} table {{ border-collapse:collapse; width:100%; }}
    th,td {{ border:1px solid #bcccdc; padding:.55rem; text-align:left; vertical-align:top; }} th {{ background:#f0f4f8; }}
    pre {{ background:#f5f7fa; border:1px solid #bcccdc; overflow:auto; padding:1rem; white-space:pre-wrap; }}
    code {{ overflow-wrap:anywhere; }} .present,.complete {{ color:#176b3a; font-weight:700; }} .missing,.incomplete {{ color:#a61b1b; font-weight:700; }}
    .note {{ background:#fffbea; border-left:.3rem solid #d69e2e; padding:.7rem 1rem; }}
  </style>
</head>
<body>
  <h1>Lab 6: Continuous Integration with GitHub Actions</h1>
  <table>
    <tr><th>Learner</th><td>{html.escape(learner)}</td></tr>
    <tr><th>Generated</th><td>{html.escape(generated_at)}</td></tr>
    <tr><th>Overall completeness</th><td class="{overall}">{overall}</td></tr>
    <tr><th>Repository revision</th><td><a href="{html.escape(repository_url)}/commit/{html.escape(commit)}">{html.escape(commit)}</a></td></tr>
    <tr><th>Pull request</th><td><a href="{html.escape(pr_url)}">{html.escape(pr_url)}</a></td></tr>
    <tr><th>Failed run</th><td><a href="{html.escape(failed_run_url)}">{html.escape(failed_run_url)}</a></td></tr>
    <tr><th>Successful run</th><td><a href="{html.escape(successful_run_url)}">{html.escape(successful_run_url)}</a></td></tr>
    <tr><th>Workflow at revision</th><td><a href="{html.escape(workflow_url)}">{html.escape(workflow_url)}</a></td></tr>
    <tr><th>Checker version</th><td>{CHECKER_VERSION}</td></tr>
  </table>

  <h2>Completeness</h2>
  <table><thead><tr><th>Required evidence</th><th>Status</th><th>Identifier</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table>

  <h2 id="decisive-run-evidence">Decisive run evidence</h2>
  {evidence_block("Failed coverage run", failed_source, failed_excerpt, failed_source in withheld)}
  {evidence_block("Successful coverage and pipeline run", successful_source, success_excerpt, successful_source in withheld)}

  <h2 id="workflow-at-the-reported-revision">Workflow at the reported revision</h2>
  <pre>{html.escape(workflow_shown)}</pre>

  <h2>Staff spot checks</h2>
  <p class="note">This checker confirms objective structure and matching saved evidence only. Answer these separately in Canvas; it does not judge either answer.</p>
  <ol>
    <li><strong>Quality gate:</strong> explain why the failed run failed, why the later run passed, and one thing coverage cannot establish about test quality.</li>
    <li><strong>CI design:</strong> justify the runner and lightweight workload choices, including one cost or security implication of another strategy.</li>
  </ol>

  <h2>Safety check</h2>
  <p>The checker scans the workflow and complete saved text files for common plaintext credential patterns, then includes only the decisive lines. Review the finished report before uploading it.</p>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Lab 6 CI HTML report and JSON manifest without contacting GitHub or rerunning Actions.")
    parser.add_argument("--learner", required=True)
    parser.add_argument("--repository-url", required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--failed-run-url", required=True)
    parser.add_argument("--failed-log", required=True, type=Path)
    parser.add_argument("--successful-run-url", required=True)
    parser.add_argument("--successful-log", required=True, type=Path)
    parser.add_argument("--output-dir", default=Path("submission"), type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    if root_result.returncode != 0:
        print("Run this command from inside the lab-github-actions repository.", file=sys.stderr)
        return 2
    root = Path(root_result.stdout.strip())
    required_inputs = {"failed run log": args.failed_log, "successful run log": args.successful_log}
    missing = [f"{label}: {path}" for label, path in required_inputs.items() if not path.is_file()]
    if missing:
        print("Missing required saved evidence:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 2

    head_result = run_git(root, "rev-parse", "HEAD")
    workflow_path = root / WORKFLOW_PATH
    if head_result.returncode != 0 or not workflow_path.is_file():
        print(f"The repository needs a commit and {WORKFLOW_PATH}.", file=sys.stderr)
        return 2
    head = head_result.stdout.strip()
    repository_url, repository = github_repository(args.repository_url)
    origin_result = run_git(root, "remote", "get-url", "origin")
    origin_url, origin_repository = github_repository(origin_result.stdout) if origin_result.returncode == 0 else ("origin-not-found", None)
    repository_ok = repository is not None and repository == origin_repository and repository_url.lower() == origin_url.lower()

    pr_url, pr_ok = github_evidence_url(args.pr_url, repository, "pull_request")
    failed_run_url, failed_url_ok = github_evidence_url(args.failed_run_url, repository, "run")
    successful_run_url, successful_url_ok = github_evidence_url(args.successful_run_url, repository, "run")
    distinct_runs = failed_run_url != successful_run_url

    workflow_text = read_text(workflow_path)
    config = workflow_configuration(workflow_text)
    runners = config["runners"]
    thresholds = config["thresholds"]
    runner_ok = bool(runners) and all(value == "ubuntu-latest" for value in runners)
    threshold_ok = len(thresholds) == 1 and thresholds[0] == 70
    pipeline_ok = bool(config["pipeline"])
    no_secret_dependency = not bool(config["secrets_reference"])

    tracked = WORKFLOW_PATH in run_git(root, "ls-tree", "-r", "--name-only", "HEAD").stdout.splitlines()
    clean = run_git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip() == ""
    immutable = tracked and clean and repository_ok
    workflow_url = f"{repository_url}/blob/{head}/{WORKFLOW_PATH}"

    failed_text = read_text(args.failed_log)
    successful_text = read_text(args.successful_log)
    failed_excerpt, failed_match = matching_line(failed_text, COVERAGE_LINE)
    success_excerpt, success_match = matching_line(successful_text, COVERAGE_LINE)
    score_excerpt, score_match = matching_line(successful_text, SCORE_LINE)
    configured_threshold = thresholds[0] if len(thresholds) == 1 else None
    failed_evidence_ok = bool(
        failed_match and configured_threshold is not None
        and float(failed_match.group("threshold")) == configured_threshold
        and failed_match.group("result").lower() == "not reached"
        and float(failed_match.group("total")) < configured_threshold
    )
    successful_evidence_ok = bool(
        success_match and configured_threshold is not None
        and float(success_match.group("threshold")) == configured_threshold
        and success_match.group("result").lower() == "reached"
        and float(success_match.group("total")) >= configured_threshold
    )
    score_ok = score_match is not None

    displayed = {
        "failed": local_display_path(root, args.failed_log),
        "successful": local_display_path(root, args.successful_log),
    }
    content_by_location = {
        WORKFLOW_PATH: workflow_text,
        displayed["failed"]: failed_text,
        displayed["successful"]: successful_text,
    }
    withheld = {location for location, content in content_by_location.items() if contains_secret(content)}
    secrets_ok = not withheld
    failed_identifier = "content withheld" if displayed["failed"] in withheld else (failed_excerpt or "not found")
    success_identifier = "content withheld" if displayed["successful"] in withheld else (success_excerpt or "not found")
    score_identifier = "content withheld" if displayed["successful"] in withheld else (score_match.group("score") if score_match else "not found")

    report_location = REPORT_NAME
    checks = [
        check("immutable_repository_revision", immutable, report_location, head, "The workflow is tracked, the tracked worktree is clean, and the credential-free repository URL matches origin." if immutable else "Commit tracked changes and provide the credential-free GitHub URL configured as origin."),
        check("pull_request_url", pr_ok, report_location, pr_url, "The pull request belongs to the reported repository." if pr_ok else "Provide an HTTPS pull-request URL from the reported repository."),
        check("failed_run_url", failed_url_ok and distinct_runs, report_location, failed_run_url, "The failed run URL belongs to the reported repository and differs from the successful run." if failed_url_ok and distinct_runs else "Provide a distinct HTTPS Actions run URL from the reported repository."),
        check("successful_run_url", successful_url_ok and distinct_runs, report_location, successful_run_url, "The successful run URL belongs to the reported repository and differs from the failed run." if successful_url_ok and distinct_runs else "Provide a distinct HTTPS Actions run URL from the reported repository."),
        check("github_hosted_runner", runner_ok, f"{report_location}#workflow-at-the-reported-revision", ", ".join(runners) or "not found", "The required test job uses ubuntu-latest." if runner_ok else "Configure the required test job with runs-on: ubuntu-latest."),
        check("coverage_threshold", threshold_ok, f"{report_location}#workflow-at-the-reported-revision", str(configured_threshold) if configured_threshold is not None else "not parsed", "The workflow enforces the lab's 70% coverage threshold." if threshold_ok else "Configure exactly one --cov-fail-under=70 coverage gate."),
        check("no_secret_dependencies", no_secret_dependency, f"{report_location}#workflow-at-the-reported-revision", "none referenced" if no_secret_dependency else "secrets reference found", "The workflow has no GitHub secrets context dependency." if no_secret_dependency else "Remove repository or course secret dependencies from the required workflow."),
        check("lightweight_pipeline_step", pipeline_ok, f"{report_location}#workflow-at-the-reported-revision", "prediction_pipeline_demo.py" if pipeline_ok else "not found", "The workflow executes the supplied demo pipeline." if pipeline_ok else "Add a workflow step that runs prediction_pipeline_demo.py."),
        check("failed_coverage_evidence", failed_evidence_ok, f"{report_location}#decisive-run-evidence", failed_identifier, "The saved decisive line shows total coverage below the configured threshold." if failed_evidence_ok else "Save the pytest-cov failure line showing the configured threshold was not reached."),
        check("successful_coverage_evidence", successful_evidence_ok, f"{report_location}#decisive-run-evidence", success_identifier, "The saved decisive line shows total coverage at or above the configured threshold." if successful_evidence_ok else "Save the later pytest-cov line showing the configured threshold was reached."),
        check("successful_pipeline_score", score_ok, f"{report_location}#decisive-run-evidence", score_identifier, "The successful run evidence includes the demo pipeline's R² score." if score_ok else "Save the successful run output line beginning 'Trained model score is:'."),
        check("obvious_credential_leakage", secrets_ok, report_location, "none detected" if secrets_ok else "content withheld", "No common plaintext credential pattern was found." if secrets_ok else "Remove and revoke plaintext credentials before regenerating; affected content was withheld."),
    ]

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    complete = all(item["status"] == "present" for item in checks)
    report = render_report(
        args.learner, generated_at, repository_url, head, pr_url, failed_run_url,
        successful_run_url, workflow_url, workflow_text, checks, displayed["failed"],
        failed_excerpt, displayed["successful"], success_excerpt, score_excerpt, withheld,
    )
    manifest = {
        "schema_version": "1.0",
        "lab": "Lab 6: Continuous Integration with GitHub Actions",
        "learner": args.learner,
        "generated_at": generated_at,
        "checker_version": CHECKER_VERSION,
        "complete": complete,
        "report": REPORT_NAME,
        "identifiers": {
            "repository_url": repository_url,
            "commit_sha": head,
            "pull_request_url": pr_url,
            "workflow_url": workflow_url,
            "failed_run_url": failed_run_url,
            "successful_run_url": successful_run_url,
            "runner": ", ".join(runners),
            "coverage_threshold": configured_threshold,
            "model_score": score_match.group("score") if score_match else None,
        },
        "checks": checks,
        "manual_spot_checks": ["quality_gate", "ci_design"],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / REPORT_NAME).write_text(report, encoding="utf-8")
    (args.output_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output_dir / REPORT_NAME}")
    print(f"Wrote {args.output_dir / MANIFEST_NAME}")
    print("Submission evidence is complete." if complete else "Submission evidence is incomplete; open the report for details.")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
