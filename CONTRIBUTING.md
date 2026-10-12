# Contributing Guidelines

Welcome to the team repository. To ensure code quality, security, and traceability, please adhere strictly to the following engineering workflows.

## 1. Branching and Pull Request Workflow
* Every code modification must originate from an explicitly defined Issue in the project backlog.
* Development must be isolated on a feature branch following the agreed convention: `type/issue-number-description` (e.g., `feat/26-secret-handling`).
* Direct commits to the `main` branch are strictly prohibited. All merges require an approved Pull Request (PR), an explicit code review, and passing CI tests.

## 2. Secrets and Environment Variables (Security Policy)
**CRITICAL: Never commit sensitive credentials, personal data, or system keys to the repository.**

* **The `.env` File:** All sensitive execution parameters, including API keys, authentication tokens, and private paths, must be stored exclusively within a local `.env` file on your host machine. This file is permanently ignored by source control via the `.gitignore` configuration.
* **The `.env.example` File:** When introducing a new environment variable requirement to the system infrastructure, you must declare its configuration key within the `.env.example` file. This ensures structural alignment across the team's local environments. Do not include actual operational secret values in this template.
  * *Example format inside `.env.example`:* `LLM_API_KEY=insert_your_key_here`
* **Incident Response:** In the event of an accidental credential leak into the Git commit history, notify the Tech Lead and QA & Security Lead immediately to orchestrate a key revocation and execute a repository history scrub.

## 3. Definition of Done
A contribution is only considered finalized when it satisfies all conditions specified in our team's `DEFINITION_OF_DONE.md` protocol.