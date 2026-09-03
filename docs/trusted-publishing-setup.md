# Trusted publishing setup (TestPyPI) — the account-owner steps

qhaway's release workflow publishes to TestPyPI with OIDC trusted publishing
once a publisher is configured on the TestPyPI side. That configuration lives
in the account owner's settings, so it cannot be done from this repo. It is
about five minutes:

1. Sign in at https://test.pypi.org and open the `qhaway` project.
2. **Manage → Publishing → Add a new publisher → GitHub**, with exactly:
   - Owner: `fsgeek`
   - Repository: `qhaway`
   - Workflow name: `release.yml`
   - Environment: *(leave blank)*
3. Save. Nothing else changes.

After the next tagged release succeeds via OIDC (the workflow log's publish
step will say trusted publishing was used), delete the `PYPI_DEPLOY_KEY_TEST`
repository secret and revoke that token on TestPyPI — the fallback is then
gone and no long-lived publishing credential remains anywhere.

Real PyPI is deliberately not part of this: publishing there stays a manual
`uv publish` per the controls note in `.github/workflows/release.yml`.
