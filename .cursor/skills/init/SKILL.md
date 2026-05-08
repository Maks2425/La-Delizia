---
name: init
description: Read the whole project and write a concise repository summary into a separate txt file. Use when the user asks for "/init", project onboarding, or a quick codebase digest.
disable-model-invocation: true
---

# Init Project Summary

## Purpose

Use this skill when the user asks: `/init` or asks to "читає цілий проєкт та підсомовує в окремому txt файлі".

## Output

Create or overwrite a plain text summary file in the repository root:

- `PROJECT_SUMMARY.txt`

Write the summary in Ukrainian unless the user asked for another language.

## Workflow

Copy this checklist and complete it:

```
Init Skill Progress:
- [ ] Map repository structure
- [ ] Identify app entry points and main modules
- [ ] Extract major features and user flows
- [ ] Note data/storage/configuration details
- [ ] Note how to run and verify the project
- [ ] Write PROJECT_SUMMARY.txt
```

### 1) Map repository structure

- List key top-level directories and files.
- Focus on source, templates/views, static assets, config, data, and docs.
- Ignore generated/noise folders (for example caches or virtual environments).

### 2) Identify entry points and modules

- Find backend entry point(s), route/controller files, and core domain logic.
- Find frontend templates/scripts/styles and how they connect.
- Record critical integrations (DB, APIs, auth, external services).

### 3) Extract major features

Summarize user-facing capabilities, for example:

- authentication/authorization
- menu/catalog
- booking/reservations
- checkout/orders
- chatbot/assistant

### 4) Capture data and config

- Describe where persistent data is stored (DB/files/json).
- Note important env variables and config switches.
- Mention fallback logic (if present), e.g. local auth without DB.

### 5) Run and verification notes

- Add concise steps for local run (commands only if confidently known).
- Add quick manual test checklist for key flows.

### 6) Write `PROJECT_SUMMARY.txt`

Use this structure:

```text
Project: <name>
Date: <YYYY-MM-DD>

1. Overview
<2-4 lines>

2. Architecture
- Backend:
- Frontend:
- Data storage:

3. Key Features
- ...

4. Main Routes / Flows
- ...

5. Configuration
- ...

6. How To Run
- ...

7. Quick Test Plan
- ...

8. Risks / Gaps
- ...
```

## Quality bar

- Keep it concise and practical.
- Do not invent facts not present in the codebase.
- Prefer concrete file/path references in prose when useful.
- Ensure `PROJECT_SUMMARY.txt` is always produced as the final artifact.
