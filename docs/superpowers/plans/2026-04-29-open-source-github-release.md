# Open Source GitHub Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the BIT international student toolkit as a public GitHub repository and expose a contribution link in the app UI.

**Architecture:** Keep the current professor agent as the first tool inside a broader `bit-international-students` project. Add repository hygiene at the root, put public documentation in `README.md`, and render a small external GitHub link through existing i18n strings in the React app.

**Tech Stack:** React, Vite, TypeScript, FastAPI, Docker Compose, GitHub CLI.

---

### Task 1: Repository Hygiene And Public Docs

**Files:**
- Create: `.gitignore`
- Create: `LICENSE`
- Modify: `README.md`

- [ ] **Step 1: Add a root ignore file**

Create `.gitignore` with local secrets, generated assets, dependency folders, caches, and analytics data excluded while keeping `.env.example`.

- [ ] **Step 2: Add MIT license**

Create `LICENSE` with copyright holder `Roma Khajiev`.

- [ ] **Step 3: Refresh README**

Update `README.md` so it presents `bit-international-students` as a broader open-source toolkit, explains that Professor Agent is the first tool, documents local Docker setup, admin logging env vars, and gives short contribution instructions.

### Task 2: UI Contribution Link

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh.json`
- Modify: `frontend/src/styles/bit.css`
- Modify: `frontend/src/App.test.tsx`

- [ ] **Step 1: Add translated labels**

Add `githubLink` and `githubLabel` strings in English and Chinese locale files.

- [ ] **Step 2: Render the link**

Add a small external link pointing to `https://github.com/khajiev13/bit-international-students` near the existing language switch.

- [ ] **Step 3: Style responsively**

Style the link to match the existing restrained BIT page chrome and avoid overlapping on mobile.

- [ ] **Step 4: Cover with frontend test**

Assert the app renders the GitHub contribution link with the expected URL.

### Task 3: Verification And Publish

**Files:**
- Git repository metadata

- [ ] **Step 1: Run frontend tests**

Run `npm test -- --run` in `frontend`.

- [ ] **Step 2: Run frontend build**

Run `npm run build` in `frontend`.

- [ ] **Step 3: Run backend tests**

Run `uv run python -m pytest -v` in `backend`.

- [ ] **Step 4: Initialize and inspect git**

Run `git init`, inspect `git status --short`, and confirm ignored local files are not staged.

- [ ] **Step 5: Create public GitHub repo and push**

Create `khajiev13/bit-international-students` as public, add it as `origin`, commit the intended files, and push `main`.

- [ ] **Step 6: Sync deployment**

After the UI link exists, sync the deployed Docker app on `home`, rebuild/restart, and smoke-test health plus the root page.
