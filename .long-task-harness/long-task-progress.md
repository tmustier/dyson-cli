# dyson-cli - Progress Log

## Project Overview

**Started**: 2026-01-01
**Status**: In Progress
**Repository**: https://github.com/tmustier/dyson-cli

### Project Goals

CLI refinements following cli-guidelines best practices. Improving the command-line UX with:
- Global flags (--quiet, --verbose, --no-color)
- Environment variable support (DYSON_DEVICE)
- Dry-run mode for safe previews
- Differentiated exit codes
- Progress indicators for slow operations

### Key Decisions

- **[D1]** Use CLIContext class pattern to share global state across commands (Session 1)
- **[D2]** Exit codes: 0=success, 1=error, 2=usage, 3=connection, 4=not found (Session 1)

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

### What's Not Working
- Nothing currently blocked

### Blocked On
- Nothing

---

## Session Log

### Session 1 | 2026-01-01 | Commits: pending

#### Metadata
- **Features**: cli-001 (completed), cli-002 through cli-007 (in progress)
- **Files Changed**:
  - `src/dyson_cli/cli.py` - adding CLIContext, global flags, exit codes
  - `.long-task-harness/*` - initialized harness

#### Goal
Implement CLI refinements per create-cli skill review

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

#### Decisions
- **[D1]** CLIContext class holds global state + provides print/status methods
- **[D2]** Keep legacy `console` variable for backward compatibility during refactor

#### Context & Learnings
- Reviewed CLI against steipete/agent-scripts/skills/create-cli guidelines
- click.pass_context + make_pass_decorator pattern for sharing state

#### Next Steps
1. Add DYSON_DEVICE env var to device option → cli-002
2. Add --dry-run flag to control commands → cli-003
3. Update commands to use CLIContext → cli-007

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
