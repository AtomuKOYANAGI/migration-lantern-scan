# Security

Migration Lantern Scan performs static parsing only and parses every eligible Python source file in full. It does not import target modules or execute repository tests. It does not independently access provider-credential environment variables, non-Python configuration files, or secret stores, and it does not request credentials. A secret embedded in scanned Python source is nevertheless part of the file content the parser reads, so secrets must not be stored in source. The scanner makes no provider API calls, uploads no source code, and does not modify target files.

The GitHub Action requests only `contents: read`, requires no secrets, and does not use `pull_request_target`. It runs on Python 3.11 and installs exact dependency versions from `requirements-action.lock` into a unique runner-temporary target using `--only-binary=:all:`, `--require-hashes`, and `--target`; it does not install them into the caller's Python environment. Source distributions and unlisted artifacts are rejected. Those third-party parser/runtime wheels are imported through a scanner-only module path and therefore remain part of the trust boundary. Review and pin the Migration Lantern Scan Action commit for higher-assurance environments.

The scanner itself does not upload reports. The example workflow contains a separate, optional `upload-artifact` step with seven-day retention. Reports contain source-derived relative paths, line and column positions, matched call/model identifiers, and rule/evidence metadata; they do not include source excerpts. Treat those fields as potentially confidential repository metadata and omit artifact upload where GitHub artifact storage is not approved. Before artifacts or finding details reach stdout, the CLI checks the output path and source-controlled report metadata for supported credential and unsafe-control patterns and fails without reflecting the matched value. JSON serializes non-ASCII and control characters as ASCII escapes; decoded values are unchanged. This pattern-based guard reduces accidental disclosure; it is not a general secret scanner or proof that a report is secret-free.

To bound local resource consumption, discovery stops after 50,000 non-excluded filesystem
entries, 5,000 eligible Python files, 1,000,000 bytes in one Python file, or 50,000,000
aggregate eligible Python-source bytes. Excluded trees are pruned before they consume the entry
budget. Reaching any limit emits a blocking `limit_exceeded` issue because the partial result can
contain false negatives; narrow the scan path or split an unusually large repository and rerun.

Known limitations:

- `confidence: high` requires an unambiguous provider-module import or one assignment from an
  approved SDK constructor, plus no same-named local provider module anywhere in the scanned
  repository; provider-module aliases and approved constructor import aliases are supported,
  while a receiver name by itself is only `review`;
- explicit endpoint, header, query, or HTTP transport overrides on constructors, provider modules,
  or clients downgrade to `review`; endpoint overrides supplied only through environment variables
  or through cross-file/runtime mutation are not statically resolved;
- rebinding, wrappers, object attributes, bound-method aliases, factory-returned clients, dynamic
  imports and configuration, generated code, and cloud-specific model IDs may be review-only or
  missed;
- confidence describes provider binding, not migration safety or runtime behavior;
- a clean report is not proof that a repository has no deprecated integration;
- rule evidence is a dated snapshot and can become stale.

Report suspected vulnerabilities privately through the repository's [GitHub Security Advisory form](https://github.com/AtomuKOYANAGI/migration-lantern-scan/security/advisories/new). Do not include credentials, proprietary source, or customer data. For non-sensitive questions, use the public issue templates or contact atom01090109@icloud.com.

See `SECURITY.ja.md` for Japanese.
