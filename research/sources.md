# External Sources

Record important external sources here, as required by CLAUDE.md.

For each source, record:
- title;
- URL or other locator;
- retrieval date (UTC);
- what it was used for;
- source type: official documentation, primary source, or secondary;
- verification status: documented guarantee, observed behavior, or assumption.

Entries are append-only. Mark superseded entries rather than deleting them.

## Sources

### Claude Code permissions documentation
- URL: https://code.claude.com/docs/en/permissions.md
- Retrieved: 2026-10-07
- Used for: `.claude/settings.json` deny-rule syntax, path-pattern semantics, deny/ask/allow precedence, and the limits of Read/Edit denies for Bash commands and subprocesses
- Source type: official documentation
- Verification status: documented guarantee

### Claude Code settings documentation
- URL: https://code.claude.com/docs/en/settings.md
- Retrieved: 2026-10-07
- Used for: settings-scope precedence and `.claude/settings.local.json` handling
- Source type: official documentation
- Verification status: documented guarantee

### Claude Code sandboxing documentation
- URL: https://code.claude.com/docs/en/sandboxing.md
- Retrieved: 2026-10-07
- Used for: sandbox settings keys and platform support, deferred to Phase 0 compatibility testing
- Source type: official documentation
- Verification status: documented guarantee

### Claude Code subagents documentation
- URL: https://code.claude.com/docs/en/sub-agents.md
- Retrieved: 2026-10-07
- Used for: whether permission rules apply to subagents
- Source type: official documentation
- Verification status: documented guarantee
