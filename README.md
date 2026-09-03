# Lab: Continuous Integration with GitHub Actions

In this lab, you will set up Continuous Integration (CI) using GitHub Actions.
You will practice enforcing a test-coverage threshold, running a lightweight ML demo pipeline in CI, and interpreting failed and successful quality gates.
The required workflow runs on a GitHub-hosted runner and does not use course credentials or live services.
By the end, you should understand how CI helps maintain code quality and provides fast, reproducible feedback on ML infrastructure changes.

## Step 0: Repository Setup

### Create Your Repository

1. Start from the [course Lab 6 Template Repository](https://github.com/mlip-cmu-online/lab-github-actions)
2. Click **Use this template** at the top
3. Name your repository: `lab6-actions-<your-first-name>`
4. **Important:** Set visibility to **Private**

> Keep the repository private and do not add course credentials or other secrets.
> This lab uses only the supplied fixture data and requires no live service access.

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
an optional editing and local-testing environment. The workflow itself must
still run on the GitHub-hosted runner.

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

## Step 3: Add ML Pipeline Step to the Current GitHub Actions Workflow

So far, you’ve seen how the workflow runs tests with coverage as one of the steps in the CI pipeline. Now you’ll try adding a new step.

Check `.github/workflows/ci.yml` and complete the section marked for adding a
step for running the demo pipeline end to end, so that CI executes
`prediction_pipeline_demo.py` and logs the model's R² score.

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
