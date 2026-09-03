# Lab: Continuous Integration with GitHub Actions

In this lab, you will set up Continuous Integration (CI) using GitHub Actions.
You will practice enforcing a test-coverage threshold, running a lightweight ML demo pipeline in CI, and interpreting failed and successful quality gates.
The required workflow runs on a GitHub-hosted runner and does not use course credentials or live services.
By the end, you should understand how CI helps maintain code quality and provides fast, reproducible feedback on ML infrastructure changes.

## Deliverables

- [ ] **Deliverable 1:** Link a pull request that shows one deliberately failed coverage check followed by a successful check after the tests or implementation are improved.
      Link both workflow runs, identify the line in each log that caused the result, and explain in two or three sentences when a coverage threshold is useful and what it cannot establish about test quality.

- [ ] **Deliverable 2:** Link the workflow file and a run showing that the required job executes on a GitHub-hosted runner without repository or course secrets.
      In two or three sentences, explain one situation in which a self-hosted runner might be useful and one maintenance or security cost it introduces.

- [ ] **Deliverable 3:** Link a successful workflow run in which the lightweight ML demo pipeline executes and prints its model score.
      Explain why a small reproducible pipeline check belongs in CI while full-scale model training commonly does not.


## Step 0: Repository Setup

### Create Your Repository

1. Start from the [course Lab 6 Template Repository](https://github.com/mlip-cmu-online/lab-github-actions)
2. Click **Use this template** at the top
3. Name your repository: `lab6-actions-<your-first-name>`
4. **Important:** Set visibility to **Private**

> Keep the repository private and do not add course credentials or other secrets.
> This lab uses only the supplied fixture data and requires no live service access.

### Give Course Staff Access

Before you submit, open your private repository on GitHub and select
**Settings → Collaborators → Add people**. Invite the course-staff GitHub
account named in the Canvas lab and confirm that the invitation is accepted.
For a personal-account repository, collaborator access is what allows staff to
read the private repository, pull request, workflow, and run logs. If your
repository is owned by an organization that offers repository roles, grant the
course-staff account or team the **Read** role. Never send staff a password or
access token.

### Optional: Work in a Codespace

After creating your own repository from the template, open that repository and
select **Code → Codespaces → Create codespace on main**. Wait for the setup to
finish, then verify the editing environment in its terminal:

```bash
python --version
python -m pytest -q --cov=prediction_pipeline_demo --cov-report=term-missing
```

The supplied DevContainer uses Python 3.11 and installs `requirements.txt`; it
does not need or request any repository or course secrets. A Codespace is only
an optional editing and local-testing environment. The required CI evidence
must still come from the pull-request checks and logs produced by the
GitHub-hosted runner.

### Local Setup

```bash
git clone https://github.com/<your-username>/lab6-actions-<your-first-name>.git
cd lab6-actions-<your-first-name>
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Verify Local Tests

```bash
python -m pytest -q --cov=prediction_pipeline_demo --cov-report=term-missing
```

Examine the output to understand which lines are executed and which are missing coverage.

**Key files to explore:**
- `prediction_pipeline_demo.py`
- `tests/` folder
- `.github/workflows/ci.yml`


## Step 1: GitHub Actions CI Setup

Open `.github/workflows/ci.yml` and familiarize yourself with the important terms and layout of a GitHub Actions workflow (jobs, steps, runs-on, etc.). Pay attention to the step “Run tests with coverage”.
Confirm that the required job uses `runs-on: ubuntu-latest` and that the workflow does not reference repository or course secrets.

Reproduce the command from the “Run tests with coverage” step once on your local machine. The current configuration uses a default coverage threshold of 50%:

Understand coverage:
**Default coverage threshold:** `--cov-fail-under=50`
- Coverage ≥ 50% → the GitHub Actions workflow job will succeed (CI passes).
- Coverage < 50% → the GitHub Actions workflow job will fail (CI fails).

## Step 2: Experiment with Coverage Thresholds

In Step 1, you learned what the coverage threshold means (default: 50%) when running tests locally. Now raise the threshold in the GitHub Actions workflow to **70%** and open a pull request to see how CI enforces it.

Expect the workflow to fail initially because current tests likely don’t reach 70% coverage. Your task is to determine and implement the changes needed to make it pass. This will typically require adding or completing tests to cover untested branches in `prediction_pipeline_demo.py`

Push your updates to the same PR and observe CI turning green once coverage meets or exceeds 70%.
Save the pull-request URL, the failed and successful workflow-run URLs, and the
decisive pytest-cov line from each run. Create `evidence/failed-run.txt` and paste
the failed line there. The report generator accepts either this excerpt or a
larger copied section of the run log and includes only the decisive line.

## Step 3: Add ML Pipeline Step to the Current GitHub Actions Workflow

So far, you’ve seen how the workflow runs tests with coverage as one of the steps in the CI pipeline. Now you’ll try adding a new step.

Check `.github/workflows/ci.yml` and complete the section marked for adding a
step for running the demo pipeline end to end, so that CI executes
`prediction_pipeline_demo.py` and logs the model's R² score. Save the successful
run output in the same text file as the successful coverage line.

Create `evidence/successful-run.txt` and paste both the successful pytest-cov
line and the `Trained model score is: ...` line. Keep the linked GitHub runs as
the raw evidence; the local text files make the report durable and quick to
review.

> Note: For your course project, we don’t expect you to run full training pipelines inside CI. In practice, GitHub Actions steps are best used for lightweight checks, tests, and validations. Here, the demo pipeline is included only as an exercise to illustrate how a command can be executed within a workflow.

## Optional Extension: Self-Hosted Runner

The required lab ends after Step 3.
If you want to compare runner models, you may configure a self-hosted runner on an isolated machine that you control.
Do not install a runner on a shared course VM or a machine containing sensitive data unless course staff has explicitly approved that setup.
Self-hosted workflows can execute repository-controlled code on the host, so remove the runner when the experiment is complete and do not expose credentials to the workflow.

### Setup

1. Go to: **Settings → Actions → Runners → New self-hosted runner**
2. Follow the provided commands:
   - Download runner
   - Configure with token: `./config.sh ...` (press Enter to accept defaults)
   - Start: `./run.sh`

### Update Workflow

1. Update the workflow so the job runs on your self-hosted runner.

2. Next, replace the "Set up Python" step with:
```yaml
- name: Show Python
  run: python3 --version
```
**Note:** Ensure Python 3.11 or 3.12 is installed on your self-hosted runner machine.

Push to your branch to trigger CI. Check Actions logs to verify jobs run on your machine.

After comparing the logs, restore the required workflow to a GitHub-hosted runner and remove the self-hosted runner from the repository settings and host.

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pytest Coverage](https://pytest-cov.readthedocs.io/)
- [Managing Branch Protection Rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
- [Managing Access to Personal Repositories](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration)


## Troubleshooting

**Coverage too low:**
```bash
pytest --cov=prediction_pipeline_demo --cov-report=term-missing
```
Check which lines are missing.

**Optional self-hosted runner idle:**
- Ensure self-hosted runner is running (`./run.sh`)
- Verify `runs-on` matches runner labels

**Optional self-hosted Python errors:**
- Install Python 3.11 or 3.12 on your self-hosted machine

---

## Canvas Quiz: Verify Your CI Workflow

Complete this short quiz after finishing the three required steps. The report
is the primary grading surface; Questions 2 and 3 are the two staff spot checks.
The lab is graded PASS/FAIL, and individual questions are not scored separately.

From the root of your completed repository, generate the report and matching
manifest with:

```shell
python3 scripts/generate-ci-submission.py \
  --learner "Your name" \
  --repository-url "https://github.com/YOUR-USER/lab6-actions-YOUR-NAME" \
  --pr-url "https://github.com/YOUR-USER/lab6-actions-YOUR-NAME/pull/NUMBER" \
  --failed-run-url "https://github.com/YOUR-USER/lab6-actions-YOUR-NAME/actions/runs/RUN_ID" \
  --failed-log evidence/failed-run.txt \
  --successful-run-url "https://github.com/YOUR-USER/lab6-actions-YOUR-NAME/actions/runs/RUN_ID" \
  --successful-log evidence/successful-run.txt
```

The command reads local Git metadata, the committed workflow, and the two saved
text files. It does not contact GitHub, rerun Actions, run pytest, or execute the
demo pipeline. It checks that:

* the workflow is tracked at a clean commit whose repository URL matches
  `origin`;
* the pull request and two distinct Actions run URLs belong to that repository;
* the required `test` job uses `ubuntu-latest`, enforces exactly 70% coverage, runs
  `prediction_pipeline_demo.py`, and does not reference the GitHub `secrets`
  context;
* the failed and successful pytest-cov lines match the configured threshold and
  the successful evidence includes the printed model score; and
* the included text contains no obvious plaintext credential pattern.

The command writes `submission/ci-report.html` and
`submission/ci-manifest.json`. It exits with status 0 for a complete package,
status 1 when a check is missing or inconsistent, and status 2 for invalid or
missing inputs. Open the HTML report and correct each `missing` item before
uploading it. Keep the JSON manifest with your evidence; it is not a second
Canvas submission.

### Question 1: Submission Report

**Response type:** File upload

Upload `submission/ci-report.html`. It contains:

* the private repository URL, immutable commit SHA, and pull-request URL;
* the workflow-file URL at that commit and its `runs-on` value;
* distinct failed and successful run URLs with the decisive coverage line from
  each;
* the successful run's lightweight-pipeline R² line; and
* a completeness table marking each item as present or missing.

Confirm that course staff have accepted access to the private repository before
submitting. The repository, pull request, and workflow runs remain the raw audit
evidence. Do not include credentials in the report or evidence files.

### Question 2: Quality-Gate Spot Check

**Response type:** Short answer

State the coverage threshold enforced by your completed workflow. Using the
decisive lines in your report, explain why the first run failed and the later run
passed. State one thing the threshold cannot establish about test quality.

### Question 3: CI-Design Spot Check

**Response type:** Short answer

Identify the required job's `runs-on` value and the R² score in your report.
Explain why this lightweight check fits a GitHub-hosted runner while full-scale
training might justify a different execution strategy, naming one cost or
security implication.

## Submission Automation Maintenance

The generator is a deterministic completeness checker. Its HTML and JSON use
the same check names and statuses and include only the decisive log lines. It
does not decide whether either spot-check answer is correct and does not assign
a grade. Run its focused tests with:

```shell
python3 -m unittest tests/test_generate_ci_submission.py
```
