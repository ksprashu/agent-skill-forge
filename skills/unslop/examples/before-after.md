# Examples

## Before -> After

**AI prose (bloated)**
> In today's rapidly evolving technological landscape, it is important to note that leveraging microservices can serve as a powerful paradigm for enhancing scalability, while monolithic architectures play a vital role in reducing operational overhead for smaller teams.

**Bad over-correction (clipped 8-word staccato fragments)**
> Microservices scale pieces independently. They add network overhead. Monoliths are simpler to deploy. Small teams should use monoliths.

**Unslopped (connected cause-and-effect flow)**
> Microservices let you deploy and scale individual services independently, whereas a monolith keeps everything in a single deployment unit so that small teams don't pay the operational tax of distributed tracing and network retries before they actually need horizontal scale.

---

**Technical Dossier / Readout (`R6`)**
> **AI / clipped fragments (Bad):** On token-metered endpoints, context size and thinking effort drive the cost of every turn. On request-metered endpoints one call costs one unit, whatever its size. That difference decides where bulk work should go.
>
> **Unslopped `R6` Dossier Style (Good):** Gateway endpoints split into token-metered tiers, where every turn scales with context size and reasoning effort, and flat request-metered tiers, where a call costs a single request unit regardless of payload size. Because request-metered tiers ignore token weight, high-volume mechanical loops and health monitors should run on a request-metered endpoint rather than draining your shared token budget.

---

**Code comment**
> // This comprehensive utility function is meticulously designed to sanitize and process user input in order to ensure optimal security and data integrity across the application.

**Unslopped**
> // Trim and lowercase the name; return empty string if missing.
