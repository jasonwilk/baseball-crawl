# E-008-R-01: Intent Systems Intent-Layer Approach -- Research Summary

**Produced by**: claude-architect (acting)
**Date**: 2026-02-28
**Source**: https://intent-systems.com/blog/intent-layer and https://intent-systems.com/blog/context-is-your-constraint

---

## Plain-Language Explanation

The Intent Layer is a methodology for structuring an AI-accessible "map" of a codebase by placing small, opinionated markdown files at semantic boundaries throughout the project hierarchy. Each file is called an Intent Node. When an agent works in a directory, its ancestor nodes load automatically, giving the agent a T-shaped view of context: broad orientation at the project root, narrowing to specific invariants at the directory it is working in.

The core insight is that code alone does not convey *why* things are designed a certain way -- intent nodes capture that layer of knowledge that lives in senior engineers' heads. A node explains what a subsystem is responsible for, what its entry points and contracts are, which anti-patterns to avoid, and what other parts of the system it depends on. This is meaningfully different from a README, which typically describes *what* exists; an intent node is optimized for *how an agent should reason about this area before touching it*.

The system is built around token efficiency. Rather than dumping an entire codebase into context (or forcing agents to explore blindly), intent nodes compress each semantic area into the minimum tokens needed for safe operation. A subsystem that might take 200k tokens to fully read might be accurately represented by a 2-3k token intent node. The hierarchy handles duplication via the Least Common Ancestor optimization: shared knowledge lives once at the shallowest node that covers all relevant paths, preventing the same information from appearing in multiple child nodes.

---

## Research Question Answers

**Q1: What is an "Intent Node" and what distinguishes it from a plain README or CLAUDE.md file?**

An Intent Node is a markdown file placed at a semantic boundary in a codebase whose content is explicitly optimized for agent consumption. It differs from a README in three ways: (1) it explains architectural intent and invariants, not just what the code does; (2) its structure is opinionated (purpose, entry points, contracts, anti-patterns, dependencies); and (3) it is designed to be *loaded into agent context* automatically via directory-scoped inclusion, not read by humans browsing the repo. It differs from a project-level CLAUDE.md in scope -- CLAUDE.md is global, an Intent Node is local to its semantic boundary and its children.

**Q2: How does the hierarchical loading mechanism work? What triggers a node to load, and what is the scope of each node?**

When an agent begins work in a directory, all Intent Nodes from the project root down to that directory load automatically. The trigger is directory scope -- working in `src/gamechanger/` would load root-level, `src/`, and `src/gamechanger/` nodes. The mechanism is implemented via Claude Code's existing CLAUDE.md import/include behavior (or similar tool-specific loading hooks). Each node's scope is bounded to its subtree: the `src/gamechanger/` node should only describe what a working agent needs to know about that module, not the entire project.

**Q3: What is the "Least Common Ancestor" optimization and why does it matter for token efficiency?**

The LCA optimization means that if the same piece of knowledge is relevant to two or more subtrees, it lives in the *shallowest node that covers both* -- not duplicated in each child. For example, if both `src/http/` and `src/gamechanger/` need to know that all outbound requests must use the shared session factory, that rule lives in `src/`, not in both subdirectory nodes. This prevents token waste (duplicate content loading) and prevents drift (a rule updated in one place but not the other). It is the enforcement mechanism for the principle "one source of truth, loaded to the right depth."

**Q4: What is "fractal compression" in this context and how is it implemented in practice?**

The article uses "fractal compression" to describe the recursive summarization pattern during intent layer construction: leaf nodes are captured first (via subject matter expert interviews or direct code analysis), then parent nodes are written by summarizing the leaf nodes -- not by re-reading raw code. The result is a hierarchy where each level is a compressed representation of the level below, much like how fractals repeat structure at different scales. In practice: write `src/gamechanger/` intent node first, then derive the `src/` intent node by summarizing the gamechanger node (and any sibling nodes). The compression ratio is substantial: a 200k-token codebase area might compress to 2-3k tokens at the leaf, and those leaf summaries further compress into a 1k-token parent.

**Q5: What does a concrete example look like when applied to a Python project with multiple modules?**

The article does not provide a full file listing, but the pattern is clear from the description. For a project like baseball-crawl, the intent layer would look like:

```
/ (root CLAUDE.md -- already exists)
  src/
    CLAUDE.md or AGENTS.md  -- scope: all of src/; covers code organization, testing rules, dependency policies
    gamechanger/
      CLAUDE.md             -- scope: GC module; covers API client, credential handling, rate limiting invariants
    http/
      CLAUDE.md             -- scope: HTTP layer; covers session factory contract, header requirements, no-parallel-requests rule
    safety/
      CLAUDE.md             -- scope: safety module; covers PII scanner, pre-commit hook, never-commit rules
  epics/
    CLAUDE.md               -- scope: epic/story structure; covers status lifecycle, numbering scheme, dispatch rules
  tests/
    CLAUDE.md               -- scope: test conventions; covers mocking rules, no real HTTP calls policy
```

Each file contains: purpose, entry points, key contracts/invariants, anti-patterns, and downlinks to related nodes.

**Q6: What are the stated failure modes or anti-patterns the system warns against?**

The source material identifies these failure modes:
- **Agentic search as default**: Relying on agents to explore the codebase rather than pre-providing structure. Works for small projects; fails at scale when agents miss architectural patterns.
- **Manual context engineering**: Hand-curating context bundles per task. Produces good results but is brittle, non-reusable, and takes 30-90 minutes per task -- does not scale.
- **Duplication in child nodes**: Knowledge about a shared contract appearing in multiple leaf nodes rather than at the LCA. Leads to drift and contradictions.
- **Writing top-down**: Building parent nodes before leaf nodes. Leads to speculative summaries; the correct order is leaf-first.
- **Treating it as documentation management**: Intent nodes are a token-optimization system, not a docs layer. Writing vague, narrative-style nodes wastes tokens without delivering the precision agents need.

**Q7: What tooling or agent integration is assumed or required?**

The system assumes directory-scoped markdown file loading, which Claude Code supports natively via CLAUDE.md files (imported by parent CLAUDE.md or auto-loaded per directory). The sync process (detecting which Intent Nodes are affected by a code merge and proposing updates) assumes some tooling or process for linking git diffs to the node hierarchy -- the article mentions this can be manual (5-10 min/PR) or automated. No proprietary tooling from intent-systems.com appears to be required; the methodology is implementable with any editor/agent that supports directory-scoped context files.

**Q8: Is the system designed for a specific agent platform or is it platform-agnostic?**

The system is largely platform-agnostic at the concept level. The article explicitly notes that different tools require different filenames (`CLAUDE.md` for Claude Code, `AGENTS.md` for other tools) and recommends using symlinks or careful configuration to avoid duplication across platforms. The underlying mechanism (hierarchical directory-scoped markdown files that load when an agent works in a directory) maps directly onto Claude Code's native CLAUDE.md import behavior, making baseball-crawl's current toolchain a natural fit.

---

## Baseball-crawl Applicability Assessment

| Principle | How It Works | Applicable to baseball-crawl? | Notes |
|-----------|-------------|-------------------------------|-------|
| Hierarchical intent nodes | Small markdown files at semantic directory boundaries | **Partially** | The project has CLAUDE.md at root and agent definitions in .claude/agents/. No directory-level nodes exist under src/, epics/, tests/, etc. Adding them is low-cost. |
| LCA optimization | Shared rules live in shallowest covering ancestor | **Yes** | baseball-crawl already applies this informally -- shared rules (HTTP discipline, credential handling) live in CLAUDE.md rather than repeated per-agent. Formalizing this is natural. |
| Leaf-first construction | Write leaf nodes before parent summaries | **Yes** | baseball-crawl's codebase is small enough that leaf-first construction is straightforward. The work is one-time with low maintenance cost. |
| Hierarchical auto-loading | Ancestor nodes load when agent works in a directory | **Partially** | Claude Code supports this via CLAUDE.md imports but baseball-crawl does not currently use directory-level CLAUDE.md files. The mechanism is available; the files do not exist yet. |
| Compression focus | Nodes minimize tokens, not maximize coverage | **Yes** | baseball-crawl's existing CLAUDE.md already demonstrates this preference -- it is concise and opinionated rather than exhaustive. |
| Sync process | Update intent nodes when code changes | **Weak fit** | baseball-crawl does not have a CI/CD pipeline. Sync must be manual. At this project's scale (small team, one operator), the per-PR overhead is manageable but should not be automated unless friction proves real. |
| Maintenance overhead | 5-10 min/PR if manual | **Acceptable** | With ~30 games/season and primarily Python code changes, PR frequency is low. 5-10 min overhead per PR is proportionate. |
| Investment to build | 3-5 hours per 100k tokens | **Low for this project** | baseball-crawl's src/ is small (< 1k lines of Python as of E-006). Total investment to write intent nodes for all semantic boundaries would be 2-4 hours. |

---

## Key Tensions

1. **Token efficiency vs. maintenance burden**: Intent nodes pay off when agents repeatedly need codebase orientation. For baseball-crawl's current scale (one operator, infrequent agent onboarding), the per-PR maintenance cost may exceed the token savings for months. The break-even point improves as the project grows.

2. **Specificity vs. drift**: The more specific and invariant-rich an intent node is, the more useful it is to agents -- and the more likely it is to drift from the codebase as code changes. Baseball-crawl's active development means nodes will need updates after significant stories (e.g., after E-002 adds crawler code, the src/ node becomes stale).

3. **Structured context vs. story files**: Baseball-crawl already has a strong story/epic system that provides agent context at task granularity. Intent nodes provide *structural* context about the codebase, not *task* context. The two are complementary but adding intent nodes adds a second system to maintain.

4. **Platform lock-in risk**: The CLAUDE.md format is Claude Code-specific. If the project ever migrates to a different agent runtime, intent nodes would need renaming or adapting. Minor risk given the project's current toolchain.

---

## Recommendation Stub

The Intent Layer methodology is a **partial fit** for baseball-crawl in its current state. The core concept -- directory-scoped markdown files explaining local invariants -- maps cleanly onto Claude Code's CLAUDE.md import behavior and would benefit the project as it grows. However, at the current project scale (one operator, small Python codebase, low PR frequency), the full implementation with sync processes and hierarchical summarization is over-engineered. The right adoption path is selective: add 3-5 directory-level CLAUDE.md files at the highest-leverage semantic boundaries (src/, src/gamechanger/, epics/) rather than the full hierarchical build-out. This delivers 80% of the value at 20% of the maintenance cost.
