# Sample Rewrites

Rewrites showing how `unslop` removes AI bloat while keeping natural, connected cause-and-effect sentence flow instead of chopping thoughts into staccato fragments.

## Sample 1 - Technical Explanation (`R6`)

**Original (AI-ish)**
In the contemporary cloud computing paradigm, it is crucial to delve into the multifaceted challenges associated with latency optimization. Furthermore, unindexed foreign keys can serve as a significant bottleneck, underscoring the importance of proactive database management strategies that leverage modern indexing techniques to enhance overall system performance.

**Unslopped**
Unindexed foreign keys force full table scans on every join or cascade delete, which quickly becomes your primary latency bottleneck under concurrent load; adding composite indexes on those foreign-key columns keeps query times flat as the table grows.

## Sample 2 - Code Comment

**Original**
// This comprehensive helper method is meticulously engineered to leverage the full power of string processing utilities in order to sanitize and normalize user-provided names, thereby ensuring data consistency and preventing potential edge-case failures downstream.

**Unslopped**
// Trim and lowercase the name, returning an empty string if null or undefined.

## Sample 3 - Architecture Readout / Router Rate-Limit Trade-off (`R6`)

**Original (Clipped staccato fragments)**
A daily gateway budget of 50M tokens looks huge. The real bottleneck is the 4-hour rolling window cap of 5,000,000 tokens. The frontier reasoning tier charges 2x the standard coding tier on every uncached token. Running the reasoning tier for both planning and coding burns through the 5M window in 2-3 heavy multi-agent rounds.

**Unslopped (Connected cause-and-effect flow)**
While a daily gateway budget of 50M tokens looks huge on paper, the real bottleneck is the 4-hour rolling window cap of 5,000,000 tokens - and that is the limit you will actually hit first. Because the frontier reasoning tier charges 2x the standard coding tier on every uncached token, running the reasoning tier for both planning and coding burns through that 5M window in 2-3 heavy multi-agent rounds.
