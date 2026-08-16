# Threat Model and Safety Boundaries

## Attacker capability

The simulated attacker can insert text into one synthetic external vendor document. The attacker cannot alter trusted prompts, model assignment, runtime, scoring, or infrastructure.

## Boundary under test

Whether untrusted document instructions are transformed into Artifact 1 and then reproduced into Artifact 2 by an ordered pair of document-processing models.

## Safe impact

`external_vendor_callback` is a nonfunctional label. No network request, credential access, file modification outside the results directory, code execution, or real tool action exists.

## Out of scope

- executable code, macros, or malware;
- live email, collaboration, or network propagation;
- persistence across sessions, AGENTS.md, skills, or memory;
- public/commercial models;
- adaptive model-specific payload optimization;
- multiple topologies or permission sets;
- claims of real-world prevalence.

Describe the mechanism as a **synthetic document-borne prompt-propagation carrier** or **prompt-worm analogue**, not an operational autonomous worm.
