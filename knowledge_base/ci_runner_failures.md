# CI Runner Failures

## Overview

CI runner failures occur when no runner is available to execute a queued workflow job,
when a runner goes offline mid-job, or when runner registration or service startup fails.
This document covers GitHub Actions hosted and self-hosted runners, as well as general
CI/CD runner infrastructure issues.

## Common Causes

### 1. Self-Hosted Runner Offline

The runner process is not running or has lost connectivity to GitHub.

**Log patterns:**
- `The self-hosted runner is offline`
- `runner is offline`
- `Runner is not connected`
- `runner disconnected`
- `runner lost communication`

**Resolution:**
1. SSH into the runner host and check the runner service: `sudo systemctl status actions.runner.*`
2. Restart the runner service: `sudo systemctl restart actions.runner.*`
3. Check network connectivity from the runner to `github.com` and `api.github.com`
4. Review runner application logs in `_diag/` directory

### 2. No Runner Matching Requested Labels

No registered runner has all the labels required by the `runs-on:` field.

**Log patterns:**
- `No runner matching the specified labels was found`
- `Requested labels: ubuntu-latest`
- `labels were not found`
- `waiting for a self-hosted runner`
- `Job is waiting for a runner`

**Resolution:**
1. Check the `runs-on:` labels in the workflow YAML
2. Verify registered runners and their labels in **Settings → Actions → Runners**
3. Add the missing label to an existing runner or register a new runner
4. For GitHub-hosted runners, check GitHub status page for runner availability incidents

### 3. Runner Registration Failure

The runner cannot register with GitHub or fails to create a session.

**Log patterns:**
- `Failed to create a session`
- `Failed to register runner`
- `Runner registration`
- `runner listener exited`
- `actions.runner` service error

**Resolution:**
1. Re-run the runner configuration script with a fresh registration token
2. Ensure `ACTIONS_RUNNER_INPUT_TOKEN` is valid and not expired
3. Check that the runner URL and token match the target repository or organisation

### 4. GitHub-Hosted Runner Unavailable

GitHub-hosted runner capacity is temporarily exhausted or the runner image is unavailable.

**Log patterns:**
- `Waiting for a hosted runner to become available`
- `github-hosted runner`
- `queued waiting for runner`
- `runner did not pick up job`

**Resolution:**
1. Check [GitHub Status](https://githubstatus.com) for runner capacity incidents
2. Add a retry on the workflow or use `concurrency:` to queue jobs
3. Consider self-hosted runners for critical workloads

### 5. Runner Service Stopped

The operating system service for the runner process has stopped unexpectedly.

**Log patterns:**
- `runner service stopped`
- `runner service failed`
- `actions-runner` exited

**Resolution:**
1. Inspect OS service logs: `journalctl -u actions.runner.* -n 100`
2. Check for OOM kills or disk space issues
3. Configure the service for automatic restart: `sudo ./svc.sh install && sudo ./svc.sh start`

## Prevention

- Monitor runner health with a ping workflow or external monitoring
- Use `concurrency:` groups to avoid overwhelming self-hosted runners
- Keep the runner application updated: `./run.sh --version`
- Configure `runs-on: [self-hosted, linux]` with at least one online runner always available
- Enable runner auto-scaling for high-demand environments

## Technology Metadata

- **technology**: github_actions
- **pipeline_stage**: runner_provisioning
- **category**: ci_runner_failure
