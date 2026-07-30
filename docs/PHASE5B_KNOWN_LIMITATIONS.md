# Phase 5B — Known Limitations

1. Real GitHub App smoke (public HTTPS) is optional/manual — CI uses FakeGitHubProvider.
2. One active GitHub connection per project (MVP).
3. Background processing uses delivery rows + BackgroundTasks (no Celery).
4. Contents: Read not requested; workflow YAML file contents not fetched unless Actions metadata suffices.
5. Email/Slack notifications still out of scope.
6. Self-healing (rerun workflows, patch IAM) explicitly out of scope.
7. Local Docker frontend remains Vite-dev via compose bind-mount (unchanged from 5A).
