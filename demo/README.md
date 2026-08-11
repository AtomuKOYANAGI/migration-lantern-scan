# Synthetic before/after demo

`before/` intentionally combines an OpenAI Python pre-v1 call, a retired OpenAI model, an Anthropic legacy Text Completions call, and a retired Anthropic model. The version pins are evidence for the scenario only and must not be installed.

Run the free scanner:

```bash
migration-lantern-scan scan demo/before --locale en --no-fail-on-findings
migration-lantern-scan scan demo/before --locale ja --no-fail-on-findings
```

`after/` is an illustrative result of the paid, human-reviewed Migration Lantern Pilot. The free scanner never modifies code and does not generate that directory.

