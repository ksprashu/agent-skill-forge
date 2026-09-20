# Examples: Processing, Scrubbing, and Translation

This document demonstrates how the `extract-human-voice` skill processes raw conversational history, scrubs sensitive data/PII, and translates critique indicators into positive persona values.

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
  > "I have cloned the repo in /Users/developer/code/github/project. My GitHub Token is ghp_A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8. Can you push the feature branch?"
* **Scrubbed Output**:
  > "I have cloned the repo in /Users/`<USER_ID>`/code/github/project. My GitHub Token is `<REDACTED_GITHUB_TOKEN>`. Can you push the feature branch?"

---

## 2. Converting Technical Criticisms into Persona Attributes

When analyzing conversation history, the extractor searches for criticism triggers. This table illustrates how the raw frustrated dialogue is mapped to productive writing styles:

| Raw Dialogue (Identified by Trigger Words) | Extracted Persona Value | Refined Writing Rule |
| :--- | :--- | :--- |
| *"You were hung. Hello... what's happening? Still didn't work."* | **Speed-Typing Authenticity & Snippet Dialogues** | Write short, snappy, direct questions. Incorporate minor typing shortcuts (like *teh*, *anyting*) to mimic real-world conversational pacing. |
| *"The layout is pretty meh! It gives a standard table. What is this communicating? I want this presented in rich HTML."* | **Aesthetics Gating & Information Density** | Reject boring, low-information-density layouts. Strongly prefer clean, beautiful, dark-themed HTML documents with infographics and Mermaid charts where human consumption is key. |
| *"None of these models are in GA, they are all in preview. Sit in a corner and think about what you have done."* | **Strict Domain Grounding & Environment Constraints** | Rigorously cross-check environment restrictions. Ensure API calls and configurations strictly respect whether features are GA or Preview. |
| *"They are running the same task in parallel threads. Doing the same exact thing is a waste."* | **Workflow Concurrency and Thread Isolation** | Enforce clear, isolated modular boundaries. Avoid redundant parallel tasks by dividing work into independent vertical tracer bullets. |
