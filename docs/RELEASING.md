# Repository publication and release procedure

The initial authorization covered the public GitHub repository. The follow-up authorization covers
the reviewed `v0.1.0` tag, its GitHub Release, and the free GitHub Marketplace Action listing. It
does not authorize a movable `v0` tag, package-index upload, website deployment, payment setup,
sales listing, outreach, or paid-service transaction.

## Public repository publication

1. Recheck every provider URL and update `verified_on` / `checked_on` together.
2. Regenerate `requirements-action.lock` from reviewed PyPI release metadata. Retain exact
   versions and every applicable Python 3.11 wheel SHA-256, then test `--only-binary=:all:
   --require-hashes` in a fresh Python 3.11 environment.
3. Run `python -m scripts.audit_public_bundle` from the private workspace root.
4. Run pytest, Ruff, format check, strict mypy, build, and the local Action smoke tests.
5. Review the complete public inventory and confirm that it contains no private migration, apply,
   evaluation, PR, customer, credential, or proprietary rule implementation.
6. Confirm the canonical Apache-2.0 `LICENSE`, `NOTICE`, package metadata, publisher, contact,
   support, Security Advisory, privacy, and terms values.
7. Run `python -m scripts.export_public_bundle <new-empty-staging-directory>` without an override.
   The command refuses pending metadata, unresolved placeholders, an existing destination, unknown
   files, or a manifest mismatch.
8. Initialize Git only in the verified export, commit its exact inventory, create the approved
   repository, and push `main`. Never publish from the mixed private workspace root.
9. Verify the rendered README and policy links, inspect the remote file tree, and record the commit
   SHA, rule digest, dependency-lock digest, manifest digest, publication time, and operator.

## Approved `v0.1.0` Marketplace release

1. Repeat the complete public-tree audit, tests, cross-platform Action smoke tests, and manifest
   review against the exact release candidate.
2. Tag only the reviewed release commit as `v0.1.0`; do not create or move a `v0` tag under this
   authorization.
3. Publish a GitHub Release titled `Migration Lantern Scan v0.1.0` with the free-Scan boundary,
   supported platforms, report formats, security properties, and known static-analysis limits.
4. Select **Publish this Action to the GitHub Marketplace**, primary category **Code quality**, and
   secondary category **Dependency management**. Accepting GitHub's Marketplace terms and any 2FA
   challenge is an owner-only account action.
5. Verify the live Marketplace page, `@v0.1.0` workflow coordinate, release/tag commit, policy
   links, and a clean synthetic Action run. Record the release URL, commit, manifest digest, and
   publication time in the private launch log.

Future releases, a movable major tag, PyPI, a website, payment, listings, and outreach require a
new scoped approval.
