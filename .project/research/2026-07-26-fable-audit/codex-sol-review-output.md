I verified the draft against all four live Anthropic guides.

1. **BLOCKER — Lines 10–17 and 76: the facts/behavior binary is unsound.**  
   “Facts in the layer, behavior in the agent definition” leaves no home for model-independent behavioral requirements: authorization boundaries, credential handling, destructive-action rules, evidence requirements, review coverage, and mandatory use of canonical seams. The draft already contradicts its taxonomy by classifying “relay and construction discipline” as shared truth even though both prescribe behavior.  
   **Concrete fix:** Replace the binary with four layers:

   - Shared truth: domain facts and invariants.
   - Shared policy: universal safety, authorization, evidence, and protocol requirements.
   - Role contract: what each agent is responsible for.
   - Model adapter: only empirically necessary model-specific coaching.

   Enforce critical shared policy with tool permissions, tests, and validators—not prompts alone.

2. **BLOCKER — Lines 10–13 plus the stated 450KB shared layer: “shared” is being conflated with “preloaded everywhere.”**  
   Even correct facts become harmful when every role receives all of them: irrelevant instructions compete for attention, duplicate statements drift, stale facts remain salient, and contradictory rules become difficult to locate. Context-window capacity is not evidence that 450KB of instructions is behaviorally neutral. Opus 5’s guide claims strong long-context consistency, but Sonnet 5 explicitly notes that large or complex system prompts can alter thinking behavior, and its tokenizer uses about 30% more tokens for equivalent text. [Opus 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5), [Sonnet 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5).  
   **Concrete fix:** Keep one canonical knowledge base, but compile a bounded effective context per role/task. Load a short universal policy plus indexed, task-relevant fact packets. Add size budgets, duplicate/conflict linting, and tests for “lost in the middle” failures.

3. **MAJOR — Lines 15–17: “the harness’s job” is an unverified control dependency.**  
   Claude Code’s model-specific system prompts cannot be assumed to cover this repository’s measured failure modes, and the draft identifies no versioned contract proving that they do. Harness behavior can also change without a repository diff. The current rule therefore leaves the main session as the only fleet member with no repository-controlled model adapter.  
   **Concrete fix:** Record the harness version and the specific behaviors delegated to it. Where supported, inject the same evaluated model adapter into the main session. Where that is impossible, state explicitly that the behavior is uncontrolled and require main-session regression tests. Continue keeping model-specific tuning out of the universal shared layer.

4. **BLOCKER — Line 14: `model + effort` is not a sufficient execution pin.**  
   Behavior also depends on thinking mode, output-token budget, tools and permissions, timeouts, subagent limits, context/compaction behavior, and fallback policy. These differ materially: Opus 4.8 defaults to thinking off, Sonnet 5 defaults to adaptive thinking, Opus 5 defaults to thinking on, and Fable 5 supports adaptive thinking only. Fable’s guide also recommends fallback to Opus 4.8 for certain refusals—silently doing that would retain a Fable-tuned definition while running a materially different model. [Opus 4.8 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8), [Sonnet 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5), [Fable 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5).  
   **Concrete fix:** Define a versioned execution profile containing model ID or alias policy, effort, thinking mode, `max_tokens`, tools/ACLs, timeout, concurrency, subagent policy, and fallback behavior. Prohibit silent model fallback, or re-dispatch fallback runs with the fallback model’s adapter. Log the effective model and profile for every run.

5. **MAJOR — The architecture treats prompting as a control plane.**  
   A safety-critical instruction present in all prompts is still probabilistic. A model can miss it, context can obscure it, or a higher-priority harness instruction can conflict with it.  
   **Concrete fix:** Divide requirements into “prompted” and “mechanically enforced.” Tool ACLs should prevent unauthorized mutations; destructive tools should require scoped confirmation; secret/PII scanners should fail closed; output schemas and invariant checks should validate results. Prompts should explain these controls, not substitute for them.

6. **MAJOR — Lines 28–29, 36–37, and 74–75: verification guidance is internally inconsistent.**  
   The draft says explicit verification is wrong for Opus 5, then says inherited claims still require relay discipline. Fable’s guide separately recommends explicit long-run verification and fresh-context verifiers. Anthropic’s Opus 5 advice is specifically about redundant self-rechecking of the model’s own work—not eliminating evidence checks, safety preconditions, or validation of relayed claims. [Opus 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5), [Fable 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5).  
   **Concrete fix:** Replace “double-check is wrong for Opus 5” with a taxonomy:

   - Remove generic self-recheck scaffolding where evals show no benefit.
   - Retain mandatory evidence checks for inherited, external, or safety-critical claims.
   - Treat an orchestrator-assigned independent reviewer as distinct from a worker spawning agents merely to recheck itself.
   - Evaluate each verification type separately.

7. **MAJOR — Lines 78–79: the proposed validation is not a behavioral test.**  
   Asking one main model which instructions it would over-comply with is model self-report, not evidence, and cannot validate the other three models. It is especially inadequate before pruning a shared layer affecting the whole fleet.  
   **Concrete fix:** Use a representative role × model × effort evaluation matrix. Measure task success, missed invariants, unauthorized scope expansion, review recall/precision, tool-call count, latency, and tokens. Compare old/new prompts on identical tasks, canary the change, and retain a rollbackable prompt manifest.

8. **MAJOR — Lines 63–66: review-bar literalism is directionally correct, but “ask for EVERYTHING” is too literal.**  
   Anthropic documents this behavior for Opus 4.8, Opus 5, and Sonnet 5—not Fable 5. The proposed replacement can also flood the result with style preferences, duplicates, and unactionable speculation. The guides permit either a coverage-first stage or a concrete single-pass inclusion threshold. [Opus 4.8 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8), [Opus 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5), [Sonnet 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5).  
   **Concrete fix:** Say: “Enumerate every plausible defect within the defined defect taxonomy, including uncertain and low-severity candidates; exclude pure naming/style preferences; attach evidence, confidence, and estimated severity.” Then independently verify, deduplicate, and rank. For a one-pass reviewer, define concrete inclusion criteria instead of qualitative terms such as “important.”

9. **MAJOR — Lines 48–59 and 69 contain vendor over-generalizations.**  

   - “One brief instruction beats enumerating behaviors” is broader than the Fable guide, which says brief instructions can steer most behaviors and gives specific brevity/checkpoint examples.
   - “Positive examples … on every model” is not established by the Fable guide.
   - The Opus 4.8 claim that local verification injunctions were “load-bearing” is a repository inference, not a vendor claim.
   - “Safety classifiers … irrelevant to this repo” is unsafe: Fable’s guide warns that benign cybersecurity work may trigger them, and this repository includes authentication, network behavior, credential handling, and security review.
   
   **Concrete fix:** Tag every claim as `VENDOR`, `LOCAL`, or `INFERENCE`, cite the exact guide section, and qualify claims to their tested workload. Change “irrelevant” to “low expected frequency, but refusal and fallback handling remain required.”

10. **MAJOR — The model summaries omit configuration-relevant vendor deltas.**  
    Sonnet’s adaptive-thinking default, token-budget headroom, effort-dependent tool use, and advice to remove forced progress cadence directly affect production configuration. Opus 5’s longer written deliverables and thinking-disabled tool/XML artifacts matter to report and tool workflows. Fable’s longer turns require timeout, streaming, asynchronous progress, and refusal handling changes.  
    **Concrete fix:** Add a per-model “execution implications” subsection covering thinking mode, token budget, timeout/streaming, progress UX, tools, fallback, and unsupported parameters—not only prose-level prompting advice.

11. **MAJOR — Lines 36–46: the local evidence is too weakly specified to govern routing.**  
    “Best measured delivery discipline” rests on tiny counts such as 2/2 and 2/4, without task definitions, model build, effort, prompt version, scoring rules, or uncertainty. Anecdotes can identify hypotheses but should not establish fleet defaults.  
    **Concrete fix:** Link each local claim to a reproducible evaluation record containing task IDs, effective execution profile, raw outcomes, denominator, metric definition, and date. Label low-sample observations as hypotheses until replicated.

12. **MAJOR — Line 57: “provide a memory surface” omits memory governance.**  
    A self-writing production memory can preserve an incorrect lesson, mix model-specific advice into shared facts, leak sensitive data, or override newer repository truth. Six months of accumulated “lessons” will become another instruction-drift surface.  
    **Concrete fix:** Require provenance, author/effective model, evidence, owner, review status, creation date, expiry/revalidation date, supersession rules, and PII/secret scanning. Prevent unreviewed memory from becoming universal policy.

13. **MAJOR — Lines 3–6: the maintenance trigger is too narrow.**  
    Rechecking only when a fleet model changes misses edits to mutable vendor guides, harness system prompts, tool schemas, permissions, agent roles, and context-compaction behavior. There is also no documented instruction precedence when shared policy, agent definitions, and harness prompts disagree.  
    **Concrete fix:** Version the effective prompt/config manifest and capture its hash in traces. Re-run evaluations when the model, guide, harness, tool surface, shared layer, adapter, or role contract changes. Assign an owner and rollback target for every layer, and document actual prompt precedence.

**Verdict:** **Rethink.** The underlying instinct—keep model-specific coaching out of universal repository truth—is sound, but the proposed two-layer rule is not safe enough for a production fleet, especially with a 450KB universal prompt. Preserve that instinct while replacing the binary with shared truth, shared policy, role contracts, model adapters, and mechanically enforced controls; then validate the compiled effective prompts across the full fleet rather than relying on model self-description or harness assumptions.
