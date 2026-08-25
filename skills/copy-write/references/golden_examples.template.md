# Golden Examples (Template)

This document provides representative writing samples demonstrating the target tone, structural pacing, and clear technical exposition.

---

## Example 1: Introducing a Complex Architecture

> Let's look at how the gateway coordinates background workers. When an event triggers, the ingress router parses the payload, validates schema boundaries with Pydantic, and dispatches tasks to isolated worker threads. 
> 
> Instead of holding open blocking connections, the system uses WebSockets to stream progress updates back to the UI in real time.

---

## Example 2: Explaining a Design Decision

> Why choose vertical task slicing over horizontal layer separation? 
> 
> In a multi-agent system, horizontal slices force every agent to understand the full stack. Vertical slices keep the domain tightly bounded: one agent owns the contract, another owns the implementation, and a third runs the verification gates.

---

## Local Customization

To add your own private writing samples, create `references/golden_examples.local.md` (gitignored).
