# Migration Lantern Scan

[日本語](README.ja.md)

Migration Lantern Scan is a free, offline static scanner for documented OpenAI and Anthropic deprecations in Python repositories. It shows the impacted file and line, severity, provider-owned evidence, published deadline, and recommended direction, then exports JSON and Markdown for CI.

It does **not** execute repository code, call provider APIs, upload source, or modify scanned
source. It writes only the JSON/Markdown report paths you explicitly request.

## What it detects in v0.1

- retired OpenAI `gpt-5.2-chat-latest` model usage in recognized Responses and Chat Completions calls;
- retired Anthropic Claude Opus 4.1 model usage in recognized Messages calls;
- pre-v1 OpenAI Python `openai.ChatCompletion.create` syntax;
- Anthropic's legacy Text Completions `completions.create` endpoint.

Rules were rechecked on **2026-08-10** against provider-owned sources. A missing deadline is reported as “Not published”; Migration Lantern never invents one.

## Local install and scan

Python 3.11 or newer is required.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install .
migration-lantern-scan scan /path/to/repository --locale en
```

Reports are written to `migration-lantern-scan-reports/migration-lantern-scan.json` and `migration-lantern-scan-reports/migration-lantern-scan.md`.
Reports can reveal repository paths, call sites, model names, and migration timing. The sample workflow uploads them for seven days; remove that optional step or choose a shorter approved retention period for sensitive repositories.

Exit codes:

- `0`: scan completed; no CI failure was requested;
- `2`: invalid configuration or the scan could not complete safely;
- `3`: findings exist and `--fail-on-findings` was selected;
- `4`: review issues exist and `--fail-on-issues` was selected.

Read, parse, and file-limit issues always return `2` because the scan is incomplete. Dynamic model values return `4` only when `--fail-on-issues` is selected. The Action enables both fail options by default.

Japanese output:

```bash
migration-lantern-scan scan /path/to/repository --locale ja
migration-lantern-scan help-ja
```

## GitHub Action

The repository can be used directly from `main`. No version tag or GitHub Marketplace listing is
part of this initial repository publication. For production, replace `main` with a full commit SHA
that you have reviewed.

```yaml
name: Migration Lantern Scan
on: [pull_request, workflow_dispatch]
permissions:
  contents: read
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
        with:
          persist-credentials: false
      - uses: AtomuKOYANAGI/migration-lantern-scan@main
        with:
          path: .
          locale: en
          fail-on-findings: "true"
          fail-on-issues: "true"
```

For higher-assurance environments, pin third-party Actions—including Migration Lantern Scan—to reviewed commit SHAs.

## Demo

`demo/before` is synthetic and intentionally outdated. Do not install its pinned packages.

```bash
migration-lantern-scan scan demo/before --locale en --no-fail-on-findings
```

`demo/after` illustrates a human-reviewed paid-pilot result. The free scanner never rewrites code.

## Security and privacy

Migration Lantern Scan parses files locally and needs no secrets. The Action uses only `contents: read`, does not use `pull_request_target`, and does not execute target tests. See [SECURITY.md](SECURITY.md). Report vulnerabilities through the [private GitHub Security Advisory form](https://github.com/AtomuKOYANAGI/migration-lantern-scan/security/advisories/new), not a public issue.

Static analysis has limits. Receiver names are a heuristic rather than type proof, and wrappers, aliases, dynamic configuration, generated code, or cloud-specific IDs can be missed. A clean result is not a guarantee.

Each finding has a `confidence` value. `high` means LibCST resolved the call receiver to an
unambiguous `openai` or `anthropic` module import, or to one assignment from an approved SDK
client constructor, and the repository contains no same-named local module that could shadow
that provider package. Provider-module aliases and approved constructor import aliases are
resolved. A matching call shape without that proof is kept as `review`; receiver spelling alone
never earns `high`. Explicit endpoint, header, query, or HTTP transport overrides on a constructor,
provider module, or client downgrade the match to `review`. Rebinding, other imported-object
aliases, wrappers, attributes such as `self.client`, bound-method aliases, factory-returned
clients, and dynamic imports may remain review-only or outside coverage. Endpoint overrides
supplied only through environment variables, cross-file mutation, or runtime mutation cannot be
resolved statically. `confidence` is provider-binding confidence, not proof that a migration is
behaviorally safe.

## Free Scan vs Migration Lantern Pilot

| | Free Migration Lantern Scan | Paid Migration Lantern Pilot |
| --- | --- | --- |
| Detect configured deprecations | Yes | Yes, plus scoped manual investigation |
| Official evidence and deadlines | Yes | Yes |
| JSON / Markdown | Yes | Yes |
| Modify code | No | Human-reviewed migration patch |
| Tests and regression tests | No | Included for the agreed repository |
| Quality/cost/latency review | No | Included where measurable |
| Pull request | No | Draft PR after explicit repository approval |
| Support | Public issue templates | Seven-day defect-fix window |

Pilot launch price for the first three accepted projects: **USD 499** for one scoped Python repository. Acceptance depends on a private preflight questionnaire; no API key should be sent in chat or email.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy src tests
python -m build
```

## Publisher, license, and contact

- Publisher: `AtomuKOYANAGI`
- Copyright notice: `Copyright 2026 4tomStudio`
- License: [Apache License 2.0](LICENSE)
- Public support: [GitHub issue chooser](https://github.com/AtomuKOYANAGI/migration-lantern-scan/issues/new/choose)
- Public contact: [atom01090109@icloud.com](mailto:atom01090109@icloud.com)
- Privacy: [Privacy Notice](https://github.com/AtomuKOYANAGI/migration-lantern-scan/blob/main/PRIVACY.md)
- Terms: [Terms of Use](https://github.com/AtomuKOYANAGI/migration-lantern-scan/blob/main/TERMS.md)

Apache-2.0 applies only to the files distributed in this public Scan repository. It does not apply
to the private Migration Pilot implementation or customer workspaces. A package-index release,
version tag, GitHub Marketplace listing, hosted website, payment flow, or paid service publication
requires a separate release decision.
