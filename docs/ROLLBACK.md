# Release rollback

If a public rule is wrong, an Action release is unsafe, or private material is exposed:

1. Stop Marketplace promotion and mark the affected release in the README.
2. Do not rewrite a signed release silently. Create a reviewed patch release for ordinary defects.
3. Move `v0` back to the last known-good commit only after recording both SHAs and the reason; users pinned to a commit remain unaffected.
4. If private data or credentials were exposed, archive public access only with owner approval, revoke affected credentials immediately, preserve an internal incident record, and follow GitHub's sensitive-data removal process.
5. Notify affected users through the public security/release channel with facts, scope, fixed version, and mitigation—never with customer data.
6. Re-run the full public-bundle audit before republishing.

