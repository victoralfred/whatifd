# whatif verdict: Inconclusive

**Reason:** could not acquire scorer cache lock at `.whatif/cache/scorer/.lock`.
A previous run may have terminated abnormally, leaving the lock file orphaned.

[Suggested next steps ↓](#fix) · [Manifest →](manifest.json)

---

## Suggested next steps

The cache lock file shows:
- PID: 12345 (recorded)
- Hostname: ci-runner-7
- Started: 2026-04-30T14:22:00Z (4 days ago)

To recover:

1. **If you know the previous run is no longer running:**
   `whatif cache rebuild --force`
   This will rebuild the cache from scratch (slower next run, but safe).

2. **If you want to clear just the lock without rebuilding:**
   `whatif cache unlock`
   Use only if you're certain no other whatif process is using this cache.

3. **If you suspect file corruption:**
   `whatif cache verify`
   Reads all entries, reports any with checksum mismatches, optionally repairs.

This run produced no verdict. Rerun after recovery.
