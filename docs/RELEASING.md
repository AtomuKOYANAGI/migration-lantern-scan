# Repository publication and release procedure

The initial authorization covers the public GitHub repository only. It does not authorize a
version tag, GitHub Release, Marketplace listing, package-index upload, website deployment, or
paid-service transaction.

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

## Separately approved future releases

A versioned Action release may add a reviewed `v0.1.0` tag and a movable `v0` major tag. Publishing
those tags, creating a GitHub Release, listing the Action in GitHub Marketplace, or publishing the
Python package requires a separate approval and a fresh full-tree audit. Until then, examples use
`@main` and tell production users to pin a reviewed full commit SHA.
