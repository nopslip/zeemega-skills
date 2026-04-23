# Cron registration — DO NOT APPLY YET

Per the zeemap lifecycle execution plan (Phases 7 → 8), the daily audit
cron is activated **after** a successful manual run. This file documents
the exact entry to append to `~/.hermes/cron/jobs.json` when that gate
clears — it is not auto-applied by this skill.

## Entry to append

Insert into the `"jobs"` array in `~/.hermes/cron/jobs.json`. The Hermes
cron harness will generate the `id` on reload; leave it empty or pick a
short hex string.

```json
{
  "id": "",
  "name": "Zeemap Audit",
  "prompt": "Run the zeemap-audit skill. Tier 1 only — flag and report, never modify zees. Deliver the report summary to Slack with critical issues called out.",
  "skills": ["zeemap-audit"],
  "skill": "zeemap-audit",
  "model": null,
  "provider": null,
  "schedule": {"kind": "cron", "expr": "0 8 * * *"},
  "deliver": "slack",
  "enabled": true
}
```

Leave `model` and `provider` as `null` so the job uses the active default from `~/.hermes/config.yaml`. If you want to pin a specific model, use the format the gateway recognizes: e.g. `"model": "anthropic/claude-sonnet-4", "provider": "nous"` (routes through Nous/OpenRouter). Never use Anthropic internal IDs like `claude-haiku-4-5-20251001` directly — they 404 against Nous.

Schedule is daily at 08:00 local (`0 8 * * *`) — adjust `expr` to taste.
After editing, reload the gateway so the cron system picks it up:

```bash
systemctl --user restart hermes-gateway
```

## Why this is a separate step

Running an audit cron *before* the first hand-verified run risks a noisy
initial Slack post during a migration-adjacent window. Phases 7 → 8 of
the plan exist so we see the report format in person once before it
starts landing on its own every morning.
