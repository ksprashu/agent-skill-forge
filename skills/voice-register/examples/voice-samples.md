# Voice Samples — Example Profile (`examples/example-profile.md`)

Before/after rewrites across registers. "Before" is generic AI output. "After" is `unslop` plus the fictional Sam Rivera profile. Names are placeholders. Your own samples belong next to your profile (for example `~/.gemini/personas/default/voice-samples.md`), not in this repo.

## Sample A — R2: Stakeholder Email (Launch Date and Risks)

**Before**
> Subject: Update Regarding the Upcoming Service Migration
>
> Dear [Name], I hope this message finds you well. I wanted to circle back regarding the migration timeline. After careful consideration, we believe it would be prudent to leverage the existing feature flag infrastructure in order to facilitate a seamless transition. It is important to note that there are a few potential risks we should be mindful of. Please do not hesitate to reach out with any questions. Best regards, Sam

**After**
> Hi [Name],
>
> We'll migrate on Friday 14 March, behind the existing feature flag. Flag off => the old path serves traffic, so the blast radius is small.
>
> Risks:
> - Cache warm-up adds about 10 minutes of slower responses.
> - The billing export runs at 02:00 and needs a manual check.
>
> Can you confirm the date by Thursday?
>
> Cheers,
> Sam

## Sample B — R3: Technical Blog Intro

**Before**
> In today's fast-paced cloud-native landscape, organizations are increasingly embracing infrastructure as code to unlock unprecedented agility. In this comprehensive guide, we will delve into the transformative power of policy-as-code and explore how it can revolutionize your deployment workflows.

**After**
> Last month a Terraform change deleted a production bucket. The plan looked fine and two people approved it. So we put a policy check in front of every apply, and this post walks through exactly how, with the commands we run.
>
> **Gotcha:** the policy runs against the plan JSON, not the HCL, so `terraform show -json` has to be in the pipeline.

## Sample C — R4: Strategy Proposal

**Before**
> **Executive Summary**
>
> Our current on-call model plays a vital role in maintaining service reliability, but it is increasingly clear that we face significant challenges around engineer burnout. Moving forward, it is imperative that we explore a holistic approach that balances operational excellence with team wellbeing.

**After**
> **Recommendation:** move to a follow-the-sun rotation across London and Singapore by Q3.
>
> Pages outside working hours went from **41** to **67** a month this year, and **3** engineers have left citing on-call. A paved road for runbooks cuts toil, but it doesn't fix the hours.
>
> **Risk:** handover gaps at the shift boundary.
> **Rollback plan:** keep the current rota as the secondary for one quarter.

## Sample D — R5: Working Notes (live shorthand stays)

**Before**
> I wanted to note that there is currently some work in progress on the authentication module, and to be honest, it might be worth considering a refactor at some point.

**After**
> - auth module: wip, tbh needs a refactor => after the migration
> - TODO(sam): file a ticket w/ the token-refresh repro

## Sample E — R6: Technical Dossier / Readout

**Before**
> The 4-hour window caps the gateway at 5,000,000 tokens. The reasoning tier costs 2x the coding tier on every uncached token. Using the reasoning tier for planning and coding spends that window in 2-3 rounds. The coding tier does not.

**After**
> The gateway's 4-hour window caps usage at 5,000,000 tokens, and because the reasoning tier costs 2x the coding tier on every uncached token, using the reasoning tier for both planning and coding spends that window in 2-3 rounds. The coding tier does not.
