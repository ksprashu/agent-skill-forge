# Examples: Processing, Scrubbing, and Translation

This document demonstrates how the `extract-human-voice` skill processes raw conversational history, scrubs sensitive data/PII, and drafts a profile in `voice-register`'s template layout.

---

## 1. PII and Sensitive Data Scrubbing

The extractor implements regex-based security filters to make the generated reference files safe for sharing in git repositories or between teams. Below are representative examples of how raw input text is converted into clean templates:

### Example A: Scrubbing Email Addresses & Names
* **Raw Input**: 
  > "Set up standard OAuth restrictions so that only developer@example.com and anyone from corp.internal can authenticate. Ask Alex if we need other domains."
* **Scrubbed Output**:
  > "Set up standard OAuth restrictions so that only `<EMAIL>` and anyone from `<COMPANY_DOMAIN>` can authenticate. Ask `<USER_NAME>` if we need other domains."

### Example B: Scrubbing Internal Project and Domain Paths
* **Raw Input**:
  > "Deploy this microservice under the microservice.corp.internal cloud project and verify the webhook at https://subdomain.corp.internal/receiver/v1."
* **Scrubbed Output**:
  > "Deploy this microservice under the `<COMPANY_DOMAIN>` cloud project and verify the webhook at `<INTERNAL_URL>`."

### Example C: Scrubbing Absolute Local Folders & API Credentials
* **Raw Input**:
  > "I have cloned the repo in /Users/developer/code/github/project. My GitHub Token is ghp_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8. Can you push the feature branch?"  <!-- host-path-ok: sample raw input for redaction -->
* **Scrubbed Output**:
  > "I have cloned the repo in /Users/`<USER_ID>`/code/github/project. My GitHub Token is `<REDACTED_GITHUB_TOKEN>`. Can you push the feature branch?"

---

## 2. From Measured Habits to a Draft Profile

The extractor counts habits and fills only those lines of the draft. Everything else stays a placeholder for you:

| Measured across your prompts | Draft line |
| :--- | :--- |
| 6 of 40 prompts use `colour`, `prioritise` | **Spelling**: British/Commonwealth (seen: colour, prioritise). <Confirm...> |
| `->` appears in 5 of 40 prompts | **Arrows and slashes**: `->` or `=>` in 12% of prompts. <Which form...> |
| No em-dashes | **Dashes**: em-dashes in 0% of prompts. <Keep, or ban?> |

It does not infer a persona from complaints or frustration. How you react to AI output is `cognitive-profiler`'s job.
