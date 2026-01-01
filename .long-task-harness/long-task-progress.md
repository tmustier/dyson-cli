# dyson-cli - Progress Log

## Project Overview

**Started**: 2026-01-01
**Status**: Complete
**Repository**: https://github.com/tmustier/dyson-cli

### Project Goals

CLI refinements following cli-guidelines best practices:
- Global flags (--quiet, --verbose, --no-color)
- Environment variable support (DYSON_DEVICE)
- Dry-run mode for safe previews
- Differentiated exit codes
- Progress indicators for slow operations
- Strict type checking with pyright

### Key Decisions

- **[D1]** Use CLIContext class pattern to share global state across commands (Session 1)
- **[D2]** Exit codes: 0=success, 1=error, 2=usage, 3=connection, 4=not found (Session 1)
- **[D3]** Use TypedDict for Config and DeviceConfig (Session 1)
- **[D4]** Create libdyson type stubs rather than using type:ignore (Session 1)
- **[D5]** Demote third-party unknown type errors to warnings in pyright config (Session 1)

---

## Current State

**Last Updated**: 2026-01-01

### What's Working
- Basic CLI with setup, list, status, on/off, fan, heat, night commands
- Global flags (--quiet, --verbose, --no-color)
- DYSON_DEVICE env var for default device
- --dry-run flag on all control commands
- Differentiated exit codes
- Early validation for speed/temperature
- Progress indicators for slow operations
- Strict type checking with pyright (0 errors, 0 warnings)

### What's Not Working
- Nothing currently blocked

### Blocked On
- Nothing

---

## Session Log

### Session 1 | 2026-01-01 | Commits: 97898f0..e654e0f

#### Metadata
- **Features**: cli-001 through cli-007 (all completed), typing (completed)
- **Files Changed**:
  - `src/dyson_cli/cli.py` - CLIContext, global flags, exit codes, type annotations
  - `src/dyson_cli/config.py` - TypedDict types
  - `pyrightconfig.json` - strict type checking config
  - `stubs/libdyson/*` - type stubs for third-party library
  - `.long-task-harness/*` - initialized harness
- **Commit Summary**: `feat: improve CLI UX`, `feat: add strict type checking`

#### Goal
Implement CLI refinements per create-cli skill review + add strict typing

#### Accomplished
- [x] Created refinements branch
- [x] Added CLIContext class with quiet/verbose/dry_run support
- [x] Added global flags (--quiet, --verbose, --no-color)
- [x] Defined exit code constants (0=success, 1=error, 2=usage, 3=connection, 4=not found)
- [x] Initialized long-task-harness
- [x] Added DYSON_DEVICE env var support via device_option decorator
- [x] Added --dry-run/-n flag to all control commands
- [x] Updated all commands to use CLIContext with proper exit codes
- [x] Added progress indicators via ctx.status() for slow operations
- [x] Added early validation for speed and temperature arguments
- [x] Added strict pyright type checking
- [x] Created TypedDict types for Config and DeviceConfig
- [x] Created type stubs for libdyson third-party library
- [x] Added type annotations to all CLI functions

#### Decisions
- **[D1]** CLIContext class holds global state + provides print/status methods
- **[D2]** Keep legacy `console` variable for backward compatibility during refactor
- **[D3]** Use TypedDict with NotRequired for optional fields (ip in DeviceConfig)
- **[D4]** Create stubs/libdyson/ for third-party types rather than type:ignore
- **[D5]** Demote reportUnknown* errors to warnings for third-party library noise

#### Context & Learnings
- Reviewed CLI against steipete/agent-scripts/skills/create-cli guidelines
- click.pass_context + make_pass_decorator pattern for sharing state
- TypedDict with total=False causes access issues; use NotRequired instead
- libdyson has no type stubs; created custom stubs in stubs/ directory
- Pre-commit hook runs pyright automatically on commits

#### Next Steps
1. Merge refinements branch to main
2. Consider adding tests
3. Update README with new CLI options

---

<!--
=============================================================================
SESSION TEMPLATE - Copy below this line for new sessions
=============================================================================

### Session N | YYYY-MM-DD | Commits: abc123..def456

#### Metadata
- **Features**: feature-id (started|progressed|completed|blocked)
- **Files Changed**:
  - `path/to/file.ts` (+lines/-lines) - brief description
- **Commit Summary**: `type: message`, `type: message`

#### Goal
[One-liner: what you're trying to accomplish this session]

#### Accomplished
- [x] Completed task
- [ ] Incomplete task (carried forward)

#### Decisions
- **[DN]** Decision made and rationale (reference in features.json)

#### Context & Learnings
[What you learned, gotchas, context future sessions need to know.
Focus on WHAT and WHY, not the struggle/errors along the way.]

#### Next Steps
1. [Priority 1] → likely affects: feature-id
2. [Priority 2]

-->
