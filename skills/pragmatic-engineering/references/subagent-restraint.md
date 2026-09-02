# Subagent Restraint & Anti-Stalling Protocol

Use this reference to guide subagent delegation decisions and maintain high execution velocity.

## 1. The Cost of Subagent Delegation

Every subagent invocation incurs:
- Context replication overhead (~2k-5k tokens per spawn).
- Communication message round-trips.
- Review and synchronization burden on the primary agent.

Subagents are NOT a substitute for single-threaded focused execution.

---

## 2. Delegation Decision Rubric

| Scenario | Recommendation | Rationale |
|---|---|---|
| Single-file bug fix or refactor | **Primary Agent Only** | Direct execution is faster, safer, and cleaner |
| Feature addition across 1-3 files | **Primary Agent Only** | Preserves linear context and reasoning chain |
| Code review / sanity check | **Primary Agent Only** | Primary agent must review code directly anyway |
| Independent search across 3+ unrelated repos | **Authorized Subagents** | Truly parallel, non-overlapping exploration |
| Large parallel migration of 10+ decoupled packages | **Authorized Subagents** | Bounded, independent work units |

---

## 3. Anti-Stalling Protocol

To eliminate ceremonial stalling:
1. **Cap Pre-Flight Reads**: Read only the 3-5 files directly related to the entry point and requirement.
2. **No Redundant Reconnaissance**: Do not run repetitive `git status`, `git diff`, or directory listing commands without intervening code changes.
3. **Immediate Action**: Transition from inspection to test execution/editing within 2 tool calls.
4. **Direct Communication**: State what was done succinctly. Do not write verbose conversational essays before executing tool actions.
