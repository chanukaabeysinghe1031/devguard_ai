---
provider: npm
title: NPM Dependency Resolution Failures
product: npm
source_url: https://docs.npmjs.com/common-errors
version: 1.0
---

# Dependency Failure Guidance

Package manager failures such as `npm ERR!` or `ERESOLVE` indicate unresolved or conflicting dependencies.

## Remediation

1. Inspect the conflicting package versions in the error output.
2. Align dependency ranges or use an approved resolution strategy.
3. Clear and regenerate the lockfile when policy allows.
4. Re-run install in CI with the same Node version as local development.

## Prevention

Pin engines, commit lockfiles, and fail CI on peer dependency conflicts early.
