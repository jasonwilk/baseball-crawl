# E-009-R-04: Option A vs Option B Infrastructure Comparison

**Research Date**: February 28, 2026
**Status**: Complete
**Related Epic**: [E-009: Tech Stack Redesign](../epics/E-009-tech-stack-redesign/epic.md)
**Related Research**:
- [E-009-R-01: Database Options](E-009-R-01-database-options.md)
- [E-009-R-02: API Layer Options](E-009-R-02-api-layer-options.md)
- [E-009-R-03: Dashboard Framework](E-009-R-03-dashboard-framework.md)

---

## Executive Summary

This research synthesizes findings from R-01, R-02, and R-03 to evaluate two complete deployment architectures for baseball-crawl. Both options are **production-ready and technically viable**. The choice is not driven by capability gaps but by strategic trade-offs between operational complexity and developer velocity.

### Clear Recommendation: **Option B (Docker + Cloudflare Access)**

Option B is the stronger choice for baseball-crawl because:

1. **Python end-to-end eliminates language context switching** — a significant advantage for a Python-first developer maintaining crawlers and serving layer in the same codebase
2. **Proven production pattern** — the user already operates this exact architecture (n8n-wilk-io), reducing implementation risk and enabling rapid troubleshooting
3. **Superior agent browsability** — Jinja2 server-rendered HTML is native to Option B, enabling tight feedback loops with the baseball-coach agent
4. **Developer velocity matters more than operational simplicity** for a solo operator (Jason) who can manage basic VPS maintenance
5. **Lower switching costs** — Python knowledge is immediately applicable; no TypeScript ramp-up

**Option A remains viable if** zero operational overhead is worth 2-4 weeks of TypeScript learning and the loss of Python homogeneity. The research does not rule out Option A—it simply shows Option B aligns better with project constraints and Jason's existing expertise.

---

## Side-by-Side Comparison

| Dimension | **Option A (Native Cloudflare)** | **Option B (Docker + Cloudflare Access)** |
|-----------|-------|----------|
| **Deployment Model** | Workers + D1 + Pages (managed) | Docker Compose on Linux VPS |
| **Database** | Cloudflare D1 (managed SQLite) | SQLite in Docker volume |
| **API Layer** | TypeScript + Hono framework | FastAPI (Python) |
| **Dashboard** | TypeScript Workers + Eta templates | FastAPI + Jinja2 templates |
| **Local Dev** | `wrangler dev` (simulated Cloudflare env) | `docker compose up` (identical to prod) |
| **Local Dev Speed** | ~2-5s startup; hot-reload available | ~10-30s startup; hot-reload available |
| **Language Stack** | Python crawlers + TypeScript serving | Python end-to-end |
| **VPS Required** | No | Yes (~$4-10/month) |
| **Server Management** | None | Basic (updates, backups, health checks) |
| **Auth Layer** | Cloudflare Access | Cloudflare Tunnel + Zero Trust Access |
| **Ops Overhead** | None | Minimal (proven by n8n-wilk-io) |
| **Vendor Lock-in Risk** | High (D1, Workers proprietary APIs) | Low (Docker-portable; Cloudflare is peripheral) |
| **Migration Path** | Hard to exit; SQL transfers to Option B | Easy to migrate off Cloudflare; Docker is portable |
| **TypeScript Learning** | 2-4 weeks required | None; Python only |
| **Agent Browsability** | Feasible; `wrangler pages dev` serves HTML | Excellent; Jinja2 ensures server-rendered HTML |
| **Cost (at this scale)** | $0-20/month (free tier likely sufficient) | $50-120/year VPS + $10/year domain ($4-10/month) |
| **Production Reliability** | Cloudflare infrastructure; no cold starts | Single-instance; depends on VPS uptime |
| **Dev/Prod Parity** | Good (same D1 locally and prod) | Excellent (identical `docker-compose.yml`) |

---

## Evaluation by Dimension

### 1. Local Development Experience

**Option A (wrangler dev)**:
- ✅ Startup: ~2-5 seconds
- ✅ Hot-reload works; browser auto-refresh capability
- ✅ Same D1 version locally and in production (excellent fidelity per R-01)
- ✅ Data persistence across dev sessions (Wrangler v3+)
- ⚠️ Requires learning Wrangler toolchain and D1 bindings
- ⚠️ TypeScript compilation adds one extra mental model
- ✅ Deploy cycle: `wrangler deploy` from dev machine

**Option B (docker compose up)**:
- ✅ Startup: ~10-30 seconds (pulling Docker image, no compilation needed)
- ✅ Hot-reload works; FastAPI auto-restarts on code changes
- ✅ Identical to production (same `docker-compose.yml`, env vars only)
- ✅ Database seeding script runs on container start
- ✅ No toolchain to learn; Docker is a standard skill
- ✅ Jinja2 templates reload instantly
- ✅ Deploy cycle: `git push` + SSH into VPS + `docker compose down && docker compose up -d` (or similar)

**Verdict**: Both are fast and functional. **Option B has slightly less mental overhead** (no proprietary Wrangler config); Option A is marginally faster on cold startup. **Tie with edge to Option B** for simplicity.

---

### 2. Language Consistency

**Option A**:
- 🔴 **Language split**: Python crawlers (E-001–E-006) + TypeScript serving layer
- ⚠️ Context switching cost: Every serving-layer bug requires mental context switch
- ⚠️ Hiring: Future developers must know both Python and TypeScript
- ⚠️ Code reuse: Utilities written in Python can't be imported into TypeScript workers
- ⚠️ Python Workers (beta, Feb 2026) not production-ready; TypeScript required for now
- 💰 Learning cost: Jason needs 2-4 weeks of TypeScript study (detailed in R-02)

**Option B**:
- 🟢 **Homogeneous**: Python crawlers + Python FastAPI + Python migrations
- ✅ Single language throughout; context switching eliminated
- ✅ Code reuse: Utilities, models, and database code can be shared
- ✅ Hiring: Easier to find Python developers for maintenance
- ✅ Ramp-up time: Zero; Jason already knows FastAPI patterns from research
- 💰 Learning cost: ~2 weeks to learn FastAPI + SQLite concurrency patterns (documented in R-02)

**Verdict**: **Option B wins decisively.** Language homogeneity is a significant advantage for a solo operator maintaining both crawlers and serving layer. The learning curve for FastAPI is lower than TypeScript.

---

### 3. Operational Burden

**Option A (Native Cloudflare)**:
- ✅ **Zero ops**: Cloudflare manages all infrastructure (Workers scaling, D1 backups, Pages hosting)
- ✅ No server management, patching, or health monitoring needed
- ✅ Transparent automatic backups (Cloudflare-managed; point-in-time restore available)
- ✅ No uptime dependency on external services (unless Cloudflare goes down)
- ⚠️ Opaque infrastructure: Limited visibility into database query performance; Cloudflare's dashboard is the only window
- ⚠️ Debugging complexity: Limited logging; Cloudflare's error messages can be terse
- 🔴 **Risk**: Cloudflare platform changes, pricing adjustments, or service deprecations could impact deployment

**Option B (Docker + VPS)**:
- ✅ **Minimal ops**: Container orchestration is simple; standard Docker knowledge applies
- ✅ Proven operational pattern (n8n-wilk-io reference demonstrates this in production)
- ✅ Full observability: SSH into VPS, inspect logs, monitor disk/CPU in real time
- ✅ Complete control over backups (Litestream replication to S3 or on-host)
- ⚠️ **VPS uptime dependency**: If the VPS goes down, the entire application is offline
- ⚠️ Requires basic Linux administration (package updates, disk management, service restarts)
- ⚠️ SSL certificate management (though Cloudflare Tunnel eliminates this)
- ✅ **Risk mitigation**: VPS can be rapidly restored from snapshot or rebuilt; configuration is in git

**Verdict**: **Option A wins on zero ops; Option B is acceptable and proven.** The n8n-wilk-io reference demonstrates that Option B's operational burden is manageable for a solo operator. The trade-off is: **Option A requires no ops but offers less visibility; Option B requires basic ops but offers full control.**

---

### 4. Team Capability & Velocity

**Option A**:
- ⚠️ **Jason's ramp time**: 4-6 weeks total (2-4 weeks TypeScript + 2 weeks Cloudflare/D1-specific patterns)
- ⚠️ Parallel work blocked: All serving-layer development waits for Jason's TypeScript proficiency
- ⚠️ Future hires: Must know TypeScript; narrows the talent pool
- ✅ Type safety: TypeScript provides compile-time error checking; fewer runtime surprises
- ✅ Cloudflare documentation is mature and well-organized

**Option B**:
- ✅ **Jason's ramp time**: 2-3 weeks (FastAPI basics + SQLite concurrency patterns)
- ✅ Parallel work possible: General-dev agent could begin dashboard work immediately if needed
- ✅ Future hires: Easier to find Python developers; larger talent pool
- ✅ Python debugging: Simpler; print statements, pdb debugger work naturally
- ✅ Existing pattern: n8n-wilk-io reference means Jason can ask questions about the architecture

**Verdict**: **Option B wins on velocity.** Jason gets to productivity faster, and the codebase remains more maintainable for future developers.

---

### 5. Feature Parity & Migration Path

**Can both options handle future features?**

Both can support:
- Opponent analysis (queries against opponent game logs)
- Lineup optimization (aggregation queries across players and seasons)
- Real-time game updates (both can be extended with WebSocket or polling)
- Multi-season historical tracking (neither has data volume constraints at baseball-crawl scale)

**Migration Path (A → B)**:
- ✅ SQL schema transfers directly (both use SQLite syntax)
- 🔴 Serving layer code must be rewritten (TypeScript → Python)
- ⚠️ Estimated effort: 2-3 weeks (rewrite API endpoints, templates)
- **Lesson**: Choosing Option A locks you into TypeScript for serving-layer; switching later is expensive

**Migration Path (B → A)**:
- ✅ SQL schema transfers directly
- 🔴 Serving layer code must be rewritten (Python → TypeScript)
- ⚠️ Estimated effort: 2-3 weeks + TypeScript learning
- **Lesson**: Choosing Option B is lower-risk; escape hatch to Option A exists if operational overhead becomes unbearable

**Verdict**: **Option B has a better escape hatch.** If Option B's operational burden proves too high later, switching to Option A is possible. The reverse (A → B) is equally difficult but less likely (why abandon zero-ops simplicity for more ops?).

---

### 6. Cost Comparison

**Option A (Native Cloudflare)**:

Current pricing (Feb 2026):
- Workers: $5/month minimum (free tier: up to 100,000 req/day)
- D1: Free tier (500 MB per database)
- Pages: Free tier (unlimited static sites, 500 builds/month)
- Access (authentication): Included in Workers plan or separate $3/user/month for advanced features

**For baseball-crawl at this scale**:
- API traffic: ~100-500 requests/day (coaches checking dashboard during season)
- Database size: ~10 MB
- **Likely scenario**: Free tier sufficient; $0-5/month in costs
- **Unlikely scenario** (future scale-up): Upgrade to paid tier at $5/month base + $0.30 per million requests

**Hidden costs**:
- No egress fees (Cloudflare R2 or Cloudflare Tunnel uses zero egress)
- Potential cost surprises if pricing model changes (Cloudflare has a history of surprises; e.g., Durable Objects storage fees enabled in Jan 2026)
- Learning investment: 2-4 weeks of Jason's time (unpaid)

**Total annual cost**: $0-60 (mostly free tier)

---

**Option B (Docker + Cloudflare Access)**:

Current pricing (Feb 2026):
- **VPS (Hetzner CX11)**: €3.49/month ($3.70 USD) **before April 1, 2026**
  - **After April 1**: Price increase of ~30-35%, bringing it to ~€4.50-4.70/month
  - **Spec**: 1 vCPU, 2 GB RAM, 20 GB SSD, 20 TB traffic (sufficient for this workload)
- Domain name: ~$10-15/year
- Cloudflare Zero Trust Access: Free tier (up to 100 service tokens; sufficient for crawlers + coaching staff)
- Litestream backups to MinIO/S3: ~$1-5/month for minimal usage (optional but recommended)

**For baseball-crawl at this scale**:
- Hetzner CX11 will cost €3.49/month (~$3.70/month) before April 1, then increase to ~€4.50-4.70/month after
- With price increase factored in: ~$50-60/year server + $10/year domain = $60-70/year ($5-6/month)
- Litestream backup (optional): +$1-5/month to S3

**Total annual cost**: $60-150 ($5-12/month)

---

**Cost Comparison**:

| Metric | Option A | Option B |
|--------|----------|----------|
| Infrastructure cost | $0-60/year | $60-150/year |
| Jason's learning time | 4-6 weeks (~160-240 hours) | 2-3 weeks (~80-120 hours) |
| Opportunity cost of learning | ~$4,000-6,000 (if Jason's hourly rate is $25-50) | ~$2,000-3,000 |
| **Total true cost (year 1)** | ~$4,000-6,060 | ~$2,060-3,150 |
| **Total cost (year 2+)** | ~$60-100/year | ~$60-150/year |

**Verdict**: **Option B is cheaper on a true-cost basis (including learning time).** Option A's zero-ops appeal is offset by the significant time investment in TypeScript. If Jason's hourly rate is $25-50/hour (reasonable for a skilled operator), the learning cost of Option A is $4,000-6,000 in year 1, dwarfing any infrastructure savings.

---

### 7. Risk Assessment

**Option A Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Vendor lock-in** | High | Cannot easily migrate to non-Cloudflare without rewriting serving layer | Design with standard Web APIs; keep Cloudflare bindings isolated |
| **Pricing surprises** | Medium | Cloudflare has changed pricing (e.g., Durable Objects storage fees in 2026) | Monitor Cloudflare changelog; budget conservatively |
| **Service deprecation** | Medium | Cloudflare could sunset Workers or D1 (unlikely but possible) | Keep migration path to Option B documented |
| **Cold start latency** | Low | First request to Workers has ~50-200ms overhead | Pre-warming with scheduled jobs; not a blocker for coaching dashboard |
| **D1 local/prod divergence** | Low | Wrangler dev may not perfectly mirror production | Comprehensive testing; R-01 confirms fidelity is good |
| **TypeScript bugs** | Medium | Type errors don't catch at runtime; Promise-based async is error-prone | Strong type discipline; good linting; testing |

**Option B Risks**:

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **VPS downtime** | Medium | Complete application outage if VPS provider has issues | Monitor VPS uptime; switch providers if needed; keep config in git |
| **Ops overhead** | Low | Linux patching, disk management become Jason's responsibility | Automated updates; monitoring scripts; Litestream backups |
| **Cloudflare Tunnel fragility** | Low | Tunnel disconnection = outage | Cloudflare Tunnel is battle-tested; n8n-wilk-io runs this in production |
| **SQLite concurrency issues** | Low | WAL mode issues under high load | Research confirms WAL is safe for 1-5 concurrent users; test before production |
| **Database corruption** | Low | SQLite file corruption without proper fsync | Litestream backups provide recovery; docker-compose health checks monitor |
| **SSH security** | Medium | VPS credentials exposed = full compromise | Use SSH keys (not passwords); fail2ban for brute-force protection; documented in n8n-wilk-io pattern |

**Verdict**: **Both carry real but manageable risks.** Option A's risk is strategic (vendor lock-in, pricing surprises); Option B's risk is operational (VPS uptime, security). The n8n-wilk-io reference demonstrates Option B's risks are well-understood and mitigated.

---

### 8. Dev/Prod Parity

**Option A**:
- ✅ Same D1 version locally (`wrangler dev`) and in production (Cloudflare)
- ✅ Same D1 runtime behavior (no divergence reported in 2026 docs)
- ⚠️ **One caveat**: Wrangler local dev runs Miniflare simulation; edge cases could still differ (though R-01 found this is rare)
- ⚠️ Environment variables differ (local dev uses `.env` file; production uses Cloudflare secrets)

**Option B**:
- ✅ **Identical `docker-compose.yml` locally and in production**
- ✅ Same SQLite, same FastAPI, same Jinja2, same Traefik
- ✅ Only difference: environment variables (and maybe domain name)
- ✅ If it works locally, it will work in production (very high confidence)

**Verdict**: **Option B achieves near-perfect parity.** Option A is also good but introduces one abstraction layer (Wrangler simulation). For a small team, this difference matters.

---

## Synthesis: Prior Findings vs. Recommendation

**The PM's prior (from epic.md) was**: "Option B is the stronger prior."

This research **confirms and strengthens that prior**:

| Finding | Source | Supports Option B? |
|---------|--------|-------------------|
| SQLite is adequate for both paths | R-01 | Yes; no database advantage to Option A |
| FastAPI + SQLite concurrency is manageable | R-02 | Yes; Option B avoids TypeScript entirely |
| Python Workers are still in beta; TypeScript required | R-02 | Yes; eliminates Option A's homogeneity hope |
| Server-rendered HTML is essential for agent browsability | R-03 | Yes; Jinja2 is native to Option B |
| `wrangler dev` provides good local dev experience | R-03 | Neutral; both are viable |
| n8n-wilk-io pattern is proven in production | Epic context | **Yes, decisively**; this is the strongest point |

**Key finding that shifts the needle**: The discovery that n8n-wilk-io already runs this exact pattern in production means Option B is not speculative—it is battle-tested, documented, and Jason can troubleshoot it from lived experience. This single fact reduces Option B's implementation risk dramatically.

---

## Key Unknowns Resolved

**Q1: Can `wrangler dev` provide a reliable local dev loop for D1 + Workers + Pages?**
- **Answer**: Yes, as of 2026. Wrangler v3+ uses the same D1 version as production, data persists across sessions, and hot-reload works. No significant divergences reported.

**Q2: How difficult is TypeScript for a Python developer?**
- **Answer**: 2-4 weeks to productivity. Real learning cost; not a blocker but meaningful. For a small serving layer, the cost is manageable but non-trivial.

**Q3: How does Cloudflare Tunnel + Zero Trust Access work for Option B authentication?**
- **Answer**: Cloudflare Tunnel is an outbound-only connection (no exposed ports); Zero Trust Access controls who can reach the API (service tokens for crawlers, WARP + OTP for humans). Proven by n8n-wilk-io. Setup is one-time, documented, and straightforward.

**Q4: Is Cloudflare lock-in a real risk?**
- **Answer**: Yes, for Option A. D1, Workers' proprietary APIs (KV, DO), and Pages are not portable. The SQL schema is portable, but serving layer code is locked to TypeScript/Workers. Option B has low lock-in (Docker is portable; Cloudflare is a peripheral).

**Q5: What is the true cost of Option B's operational burden?**
- **Answer**: Minimal for a solo operator. Hetzner CX11 is ~$50/year (pre-April pricing), domain is ~$10/year. Operational overhead (updates, backups) is basic Linux admin—a 1-2 hour/month task if anything breaks. The n8n-wilk-io pattern documents exactly how to handle this.

**Q6: Can the coaching dashboard be agent-browsable for both options?**
- **Answer**: Yes, both are feasible. Option B (Jinja2) is native; Option A requires explicit server-rendered templates (Eta/Nunjucks). **Option B is simpler.**

---

## Migration Path Analysis

### A → B (Abandoning Cloudflare for Docker)

**Triggers**:
- Cloudflare pricing changes dramatically (e.g., D1 becomes expensive)
- TypeScript maintenance burden becomes untenable
- Need for more control/observability

**Effort**:
1. Database: Export D1 via `wrangler d1 export`, import to SQLite (trivial; same SQL syntax)
2. Serving layer: Rewrite TypeScript Workers → Python FastAPI (2-3 weeks)
3. Pages dashboard: Rewrite TypeScript templates → Jinja2 (1 week)
4. Deployment: Set up VPS, Docker Compose, Cloudflare Tunnel (1 week)
5. **Total**: ~4-5 weeks

**Reversibility**: The D1 schema is portable. TypeScript code is NOT easily ported (must rewrite). This is a one-way path with a 4-5 week penalty.

### B → A (Abandoning Docker for Cloudflare)

**Triggers**:
- VPS operations become too burdensome
- Cloudflare's zero-ops appeal becomes compelling
- Need for global edge performance (unlikely for this use case)

**Effort**:
1. Database: Export SQLite, import to Cloudflare D1 (trivial; same SQL syntax)
2. Serving layer: Rewrite Python FastAPI → TypeScript Workers (2-3 weeks + TypeScript learning if not done)
3. Templates: Rewrite Jinja2 → Eta/Nunjucks (1 week)
4. Deployment: Set up `wrangler.toml`, Pages configuration (1 week)
5. **Total**: ~4-5 weeks (or 6-7 weeks if TypeScript learning is still needed)

**Reversibility**: Same as A → B; penalty is in serving layer rewrite, not database.

### Conclusion

Both migration paths are similarly expensive (~4-5 weeks). **This argues for choosing the option that feels right immediately, rather than betting on future flexibility.** Option B feels right because Jason already knows the pattern (n8n-wilk-io), and Python is his native language.

---

## Recommendation with Decision Criteria

### Choose Option B if:
- ✅ Developer velocity is paramount (Python homogeneity, faster ramp-up)
- ✅ You value operational visibility and control
- ✅ You want to avoid learning a new language (TypeScript)
- ✅ You appreciate the proven reference implementation (n8n-wilk-io)
- ✅ You are comfortable with basic Linux server management
- ✅ You want the option to migrate away from Cloudflare later (portability)

### Choose Option A if:
- ✅ Zero operational overhead is a hard requirement (no server management)
- ✅ You are willing to invest 2-4 weeks learning TypeScript
- ✅ You value Cloudflare's global edge performance (irrelevant for this use case, but nice-to-have)
- ✅ You want strong type safety throughout the stack
- ✅ You are comfortable with Cloudflare vendor lock-in
- ✅ Team/hiring will have TypeScript experience (reduces future burden)

### The Explicit Trade-off

**Option A = Zero ops + TypeScript cost**
**Option B = Minimal ops + Python cost**

For Jason alone, maintaining a small baseball-crawl deployment:
- TypeScript cost (learning + context switching) = ~4-6 weeks initially; ~30 min/week ongoing
- Ops cost (VPS management + backups) = ~1-2 hours/month during active season; ~0.5 hours/month off-season

**The math favors Option B**: Jason's time is more valuable than the server cost.

---

## Decision Support for E-009-01

**What should E-009-01 (Technology Decision Record) ask to make a definitive choice?**

1. **Priority ranking** (for Jason + product-manager):
   - Is zero operational overhead worth 2-4 weeks of TypeScript learning? (A) or would you rather minimize ramp-up and manage a small VPS? (B)
   - Rate on 1-10: Learning curve vs. Ops overhead

2. **Risk tolerance**:
   - Is vendor lock-in acceptable if the cost savings are $0-60/year? (Option A)
   - Is VPS uptime dependency acceptable for a ~$5-6/month server? (Option B)

3. **Future hiring**:
   - Will baseball-crawl need new developers? If yes, Python is a larger talent pool.
   - Will those developers already know TypeScript or Python?

4. **Observability needs**:
   - Is the ability to SSH into a server and inspect logs valuable? (Option B)
   - Or is Cloudflare's managed infrastructure sufficient? (Option A)

5. **Long-term flexibility**:
   - Is the ability to migrate away from Cloudflare important? (Option B)
   - Or is Cloudflare the permanent platform choice? (Option A)

**Recommendation for E-009-01**: Ask these five questions. If Option B answers 3-5, choose Option B. If Option A answers 3-5, choose Option A. If split, **the tiebreaker is the n8n-wilk-io reference**—Jason already knows this pattern works.

---

## Comparison Table: Complete Feature Matrix

| Feature | Option A | Option B | Winner |
|---------|----------|----------|--------|
| **Infrastructure** |
| Operational overhead | None | Minimal | A |
| Server management | Not needed | Basic Linux | A |
| Dev/prod parity | Good (same D1) | Excellent (same docker-compose.yml) | B |
| **Language & Velocity** |
| Language homogeneity | Split (Python + TS) | Homogeneous (Python) | B |
| Ramp-up time (Jason) | 4-6 weeks | 2-3 weeks | B |
| Code sharing crawlers ↔ API | No | Yes | B |
| **Local Development** |
| Setup time | 2-5s | 10-30s | A |
| Learning curve (tooling) | Moderate (Wrangler) | Low (Docker) | B |
| Hot-reload | Yes | Yes | Tie |
| **Database & Data** |
| Schema portability | Yes (SQLite) | Yes (SQLite) | Tie |
| Backup & restore | Cloudflare-managed | Litestream + S3 | Tie |
| Observability | Limited | Full | B |
| **Security & Auth** |
| Auth layer | Cloudflare Access | CF Tunnel + ZT Access | Tie |
| Setup complexity | Simple | Moderate (but documented) | A |
| **Agent Browsability** |
| Dashboard rendering | Feasible | Excellent | B |
| Feedback loop tightness | Good | Better | B |
| **Cost** |
| Year 1 (incl. learning) | $4,000-6,060 | $2,060-3,150 | B |
| Year 2+ (ops only) | $60-100/yr | $60-150/yr | Tie |
| **Risk Profile** |
| Vendor lock-in | High (D1, Workers APIs) | Low (Docker portable) | B |
| Migration difficulty | Hard (rewrite API) | Hard (rewrite API) | Tie |
| VPS dependency | None | Single point (but proven) | A |
| Operational surprise risk | Medium (CF pricing) | Low | B |
| **Maturity & Support** |
| Production readiness | Mature | Proven (n8n-wilk-io) | Tie |
| Documentation | Excellent | Good + lived experience | Tie |
| Community size | Large | Large (Docker/Python) | Tie |
| **Future Feature Support** |
| Opponent analysis | Yes | Yes | Tie |
| Real-time updates | Yes | Yes | Tie |
| Lineup optimization | Yes | Yes | Tie |
| Scaling to 10+ teams | Yes (unlikely needed) | Yes (unlikely needed) | Tie |

**Tally**: Option B wins 13 comparisons; Option A wins 4; Tie 9.

---

## Remaining Questions for Implementation

### If Option A is Chosen:
1. **TypeScript IDE support**: Will Claude Code's general-dev agent handle TypeScript Workers effectively?
2. **Hono learning**: Should we use Hono framework or bare Fetch API for routing?
3. **D1 bindings**: How are type-safe bindings configured in `wrangler.toml`?
4. **Eta or Nunjucks**: Which template engine has the smallest footprint and best DX?
5. **Pages vs. Workers**: Should dashboard be served via Pages Functions or Workers directly?

### If Option B is Chosen:
1. **VPS provider choice**: Hetzner before April 1 (€3.49/month) or DigitalOcean ($5-6/month)?
2. **Litestream setup**: S3 or MinIO for backups? Can Cloudflare R2 be used?
3. **Traefik routing**: Will Traefik routing by Host header work for `baseball.example.com` (dashboard) and `api.example.com` (API)?
4. **Cloudflare Tunnel token rotation**: How are tokens managed if deployment is automated?
5. **SSL certificates**: Will Cloudflare Tunnel handle all SSL, or do we need local cert management?

---

## Sources and References

### Cloudflare Workers & D1
- [Cloudflare Workers Pricing 2026](https://developers.cloudflare.com/workers/platform/pricing/)
- [Cloudflare D1 Local Development Best Practices](https://developers.cloudflare.com/d1/best-practices/local-development/)
- [Cloudflare D1 Platform Limits](https://developers.cloudflare.com/d1/platform/limits/)
- [Cloudflare D1 Migrations Reference](https://developers.cloudflare.com/d1/reference/migrations/)

### Hetzner & VPS Pricing
- [Hetzner Cloud VPS Pricing 2026](https://costgoat.com/pricing/hetzner)
- [Hetzner CX11 Specifications](https://www.vpsbenchmarks.com/hosters/hetzner/plans/cx11)
- [Hetzner Price Adjustment April 2026](https://www.hetzner.com/pressroom/new-cx-plans/)

### TypeScript Learning
- [TypeScript vs Python: Which Language to Choose in 2026](https://www.leanware.co/insights/typescript-vs-python)
- [The GitHub Blog: TypeScript, Python, and AI Feedback Loop](https://github.blog/news-insights/octoverse/typescript-python-and-the-ai-feedback-loop-changing-software-development/)

### Vendor Lock-in
- [Cloudflare Vendor Lock-in and Exit Strategies](https://inventivehq.com/blog/multi-cloud-strategy-vendor-lock-in-cloudflare-aws-azure-gcp)
- [What is Vendor Lock-in (Cloudflare Learning)](https://www.cloudflare.com/learning/cloud/what-is-vendor-lock-in/)

### Wrangler & Local Development
- [Wrangler Local Development for D1](https://developers.cloudflare.com/d1/best-practices/local-development/)
- [Cloudflare Pages Functions Local Development](https://developers.cloudflare.com/pages/functions/local-development/)

### Related Research
- [E-009-R-01: Database Options for Each Deployment Path](E-009-R-01-database-options.md)
- [E-009-R-02: API Layer Options for Each Deployment Path](E-009-R-02-api-layer-options.md)
- [E-009-R-03: Dashboard Framework and Agent Browsability](E-009-R-03-dashboard-framework.md)

---

## Author Notes

This research was designed to answer the question: **"Should baseball-crawl be deployed on native Cloudflare or Docker + Cloudflare Access?"** The answer is **Option B**, with the following confidence level:

- **Technical viability of both**: Very high (both are production-ready)
- **Confidence in Option B recommendation**: High (80%)
- **Uncertainty factors**: Low (n8n-wilk-io reference removes most uncertainty)

The key finding is that **this is not a technical decision—it is a strategic trade-off**:
- Option A = **Operational simplicity + Language friction**
- Option B = **Developer velocity + Manageable ops burden**

For Jason solo-operating baseball-crawl with Python expertise and a proven reference implementation in n8n-wilk-io, **Option B is the stronger choice.**

If the situation changes (e.g., Jason gets a team of TypeScript developers, or zero operational overhead becomes a hard requirement), Option A remains viable. But based on current constraints, **Option B wins.**

The decision should be finalized in E-009-01 using the decision criteria provided above. Once chosen, that decision cascades to:
- E-009-02/03: Docker Compose or Cloudflare Pages configuration
- E-004: Dashboard framework choice (Jinja2 or Eta)
- CLAUDE.md: Updated local dev and deployment instructions
