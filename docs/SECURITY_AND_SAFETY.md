# Security and Safety Boundary

## Allowed

- synthetic procurement documents;
- generated text artifacts;
- a synthetic document-control identifier;
- a nonfunctional mock action label;
- isolated model inference;
- deterministic external scoring;
- local evidence files under `/workspace`.

## Prohibited by design

- real credentials or sensitive data;
- outbound email, web requests, or messaging;
- real tool implementations;
- destructive actions;
- external target discovery;
- autonomous file or network replication;
- testing public/commercial models without authorization;
- treating calibration or POC outputs as final research findings.

## Why the neutral condition is still controlled

Neutral agents receive realistic business instructions that neither warn about nor preserve the carrier. The carrier can only influence generated text and a simulated decision. There is no external capability behind it.

## Controls

- schemas restrict output shape;
- the mock action is a string enum only;
- all inference occurs inside the rented environment;
- server processes receive only the Hugging Face credential needed for model access;
- Jupyter requires a password;
- model endpoints bind to localhost;
- evidence and source are hashed;
- an automatic timeout limits paid runtime.
