# Codelab Metadata & Schema Rules

Every Google Codelab markdown file (`index.lab.md`) MUST begin with the following YAML frontmatter block and adhere to specific structural rules.

## Metadata Block Template

```md
---
description: [The codelab description. E.g., "In this codelab you learn how to write a codelab."]
id: [The codelab identifier. Separate each word with a hyphen character.]
keywords: docType:Codelab, category:Cloud, skill:Intermediate
feedback link: https://github.com/googlecodelabs/feedback/issues/new?title=[CODELAB-ID]%20Feedback&labels=gemini,codelab&assignees=<github-handle>
authors: Prashanth Subrahmanyam
layout: paginated
---
```

### Critical Rules
- **Anti-Hallucination (Strict Schema):** You MUST NOT use `<generated content>` wrappers. You MUST NOT include keys like `summary`, `categories`, `environments`, or `status`. You MUST include the exact `---` delimiters at the beginning and end of the YAML block.
- **Authors:** Must always be "Prashanth Subrahmanyam" unless explicitly overridden.
- **Layout:** Specify `layout: paginated` for modern codelabs.
- **Description:** Use `description` instead of `summary`.
- **Keywords:** Must include `docType:Codelab` and a `category` (e.g., `category:Cloud`).

## Markdown Structure Rules

### Steps and Headings
- The Title is the first line after the metadata and uses `Heading 1` (`# My Codelab Title`).
- Each step is a `Heading 2` (`## My step title`).
- **Best Practice:** Title each step as an action (e.g., "Start virtual server" or "Download code").

### Duration
Each step can have an optional duration estimate. It must be placed immediately after the step heading.
```md
## My five-minute step

Duration: 05:00
```

### Info Boxes (Asides)
Use these for additional information, tips, or warnings. Do not indent the text inside the block.

**Positive (Tips/Best Practices):**
```md
> aside positive
This is a positive note. It's green and is used commonly for tips or best practices.
```

**Negative (Warnings/Caution):**
```md
> aside negative
This is a negative note. It's yellow and is commonly used to display cautionary or important instructions.
```

### Formatting Notes
- Avoid trailing whitespace.
- Leave blank lines around headings, code blocks, and list items.
- Use triple backticks for code blocks. Add `console` for terminal output (e.g., ` ```console `).