# Repo Issues and Incomplete Work

Audit date: 2026-05-27

Scope: local source, ignored local data under `data/`, package metadata, and lightweight verification commands. I did not make code fixes in this pass.

## Executive Summary

- The highest-risk code issue is SQL built from route parameters in `server/app.js`; several reads and one existence check interpolate user-controlled IDs directly into SQL strings.
- The quiz generation path is fragile: `TrendDiscovery` initializes `pytrends` during pipeline construction, so even `--topic` or `--no-pytrends` runs can fail before quiz generation starts when outbound network access is blocked.
- There are two incompatible quiz generator entry points. `pipeline/run_pipeline.py` saves quizzes under type folders that the server reads, while `generate_quiz.py` saves JSON directly under `data/quizzes/`, where the server will not discover it.
- Local quiz data has quality gaps: five personality quizzes have fewer than the configured seven questions, `data/quizzes/index.json` only lists one of 29 local quizzes, and there are orphan image directories plus one zero-byte image.
- There is no automated test script, lint script, or CI-style validation in `package.json`.

## Findings

### High Severity

1. SQL injection risk in API routes

   Evidence:
   - `server/app.js:198` interpolates `quizId` into `SELECT id FROM quizzes WHERE id = '${quizId}'`.
   - `server/app.js:222`, `server/app.js:229`, `server/app.js:247`, and `server/app.js:257` interpolate `quizId` into stats queries.
   - `server/app.js:282` interpolates `req.params.id` into the response lookup.

   Impact: route parameters are user-controlled. A crafted quiz or response ID can alter SQL behavior, expose data, or break queries. The file already uses prepared statements elsewhere (`server/app.js:113`), so these should be converted to bound parameters consistently.

2. Pipeline can fail before respecting `--topic` or `--no-pytrends`

   Evidence:
   - `pipeline/run_pipeline.py:175` constructs `QuizPipeline()` before generation options are applied.
   - `pipeline/run_pipeline.py:193` passes `use_pytrends=not args.no_pytrends`, but that is too late to prevent constructor work.
   - `pipeline/trend_discovery.py:37` creates `TrendReq(hl='en-US', tz=360)` in `TrendDiscovery.__init__`.
   - Verification command failed: `.\.venv\Scripts\python.exe pipeline\run_pipeline.py --type trivia --category history --topic Test --skip-images` raised a `requests.exceptions.ConnectionError` from `pytrends` while constructing `TrendReq`.

   Impact: users cannot reliably generate a quiz with an explicit topic in offline/restricted environments, even when topic discovery should be unnecessary. Defer `TrendReq` construction until `discover_topics()` actually needs pytrends, or respect `--no-pytrends` at construction time.

3. Placeholder API keys in `example.config.json` do not match code checks

   Evidence:
   - `example.config.json:3`, `example.config.json:7`, and `example.config.json:10` use `"api_key_here"`.
   - `pipeline/quiz_generator.py:27` and `pipeline/trend_discovery.py:33` only treat `"YOUR_GEMINI_API_KEY_HERE"` as a placeholder.
   - `pipeline/image_generator.py:102`, `pipeline/image_generator.py:108`, `pipeline/image_generator.py:123`, `pipeline/image_generator.py:402`, and `pipeline/image_generator.py:419` only check `"YOUR_UNSPLASH_ACCESS_KEY_HERE"` or `"YOUR_POLLINATIONS_API_KEY_HERE"`.

   Impact: a user who copies `example.config.json` without editing all keys will be treated as configured with invalid credentials, causing confusing API failures instead of graceful fallback.

4. Manual generator writes quizzes where the server does not read them

   Evidence:
   - `generate_quiz.py:54` sets `output_dir = Path("data/quizzes")`.
   - `generate_quiz.py:57` writes `data/quizzes/<id>.json`.
   - `server/app.js:85` only tries `data/quizzes/personality/<id>.json`.
   - `server/app.js:91` only tries `data/quizzes/trivia/<id>.json`.
   - `pipeline/quiz_generator.py:367` writes to `data/quizzes/<type>/<id>.json`, which matches the server.

   Impact: quizzes generated via `generate_quiz.py` can be saved and indexed but never appear in the app gallery or API. Align it with `QuizGenerator.save_quiz()` or remove the duplicate generator path.

5. Client-submitted quiz responses are under-validated

   Evidence:
   - `server/app.js:178` only checks `userName` and `answers`.
   - `server/app.js:192` stores `answers`, `outcome`, and `score` without verifying the payload against the quiz type, question count, valid answer choices, valid outcomes, or trivia score bounds.

   Impact: clients can submit impossible scores, unknown outcomes, mismatched answer counts, or malformed data, which then corrupts stats and play counts.

### Medium Severity

6. Frontend renders quiz data with `innerHTML` without escaping

   Evidence:
   - `frontend/index.html:216` builds quiz cards with template strings inserted into `grid.innerHTML`.
   - `frontend/quiz.html:397` inserts generated answer HTML.
   - `frontend/quiz.html:564` and `frontend/quiz.html:581` insert stats/results HTML.
   - `frontend/quiz.html:378` embeds `a.outcome` directly into an inline `onclick`.

   Impact: generated quiz titles, descriptions, answer text, image paths, or outcome IDs can break markup or execute script if malicious or malformed content gets into quiz JSON. Prefer DOM creation with `textContent` and event listeners.

7. Gallery filter relies on a global `event`

   Evidence:
   - `frontend/index.html:126`, `frontend/index.html:130`, and `frontend/index.html:134` call `filterQuizzes('...')`.
   - `frontend/index.html:193` uses `event.target` without accepting an event parameter.

   Impact: this works in some browsers because `event` is exposed globally, but it is not reliable. Pass `event` explicitly or derive the active button from the selected type.

8. Local quiz index is stale and mostly unused

   Evidence:
   - `data/quizzes/index.json:2` contains one quiz entry.
   - Local data audit found 29 quiz JSON files under `data/quizzes/personality` and `data/quizzes/trivia`.
   - 28 of those quiz IDs are missing from `index.json`.
   - `server/app.js:100` scans type folders directly and does not use `index.json`.

   Impact: `generate_quiz.py` maintains an index that the server ignores, while the server works from folders. This is confusing and creates stale metadata.

9. Several local quizzes are incomplete relative to configured counts

   Configured expectation:
   - `example.config.json` defines seven personality questions.

   Local data with fewer than seven personality questions:
   - `data/quizzes/personality/chinese-new-year-goodies-personality-quiz.json:9` has 2 questions.
   - `data/quizzes/personality/disneypixar-characters-personality-quiz.json:9` has 5 questions.
   - `data/quizzes/personality/personality-types-personality-quiz.json:9` has 5 questions.
   - `data/quizzes/personality/types-of-chocolate-personality-quiz.json:9` has 5 questions.
   - `data/quizzes/personality/which-personality-types-are-you.json:9` has 1 question.

   Impact: these quizzes will play, but they do not match the advertised generation settings or expected quiz length.

10. Orphan and broken local image assets

   Evidence from local data audit:
   - `data/images/7-wonders-of-the-world-personality-quiz/outcome-wise.png` is zero bytes.
   - `data/images/7-wonders-of-the-world-personality-quiz` has no matching quiz JSON ID.
   - `data/images/fast_food_restaurants-personality-quiz` has no matching quiz JSON ID.
   - `data/images/harry-potter-personality-quiz` has no matching quiz JSON ID.

   Impact: these are ignored local data assets, but they suggest failed generation runs and stale media that should be regenerated or pruned.

11. Brand naming is inconsistent

   Evidence:
   - `frontend/index.html:6` and `frontend/index.html:117` use `Quizzle`.
   - `frontend/quiz.html:148` and `frontend/quiz.html:310` use `QuizVibe`.

   Impact: users see different product names between the gallery and quiz pages.

12. Frontend depends on CDN assets at runtime

   Evidence:
   - `frontend/index.html:7` and `frontend/quiz.html:7` load Tailwind from `https://cdn.tailwindcss.com`.
   - `frontend/index.html:8-10` and `frontend/quiz.html:8-10` load Google Fonts.

   Impact: the app can render incorrectly offline or under restrictive network policies. Tailwind's CDN script is also not intended as the production build path.

13. Database persistence model is fragile for concurrent writes

   Evidence:
   - `server/app.js:69` exports the whole `sql.js` database to disk.
   - `server/app.js:209` calls `saveDatabase()` after every response submission.

   Impact: this is acceptable for a demo, but concurrent requests or process crashes can lose writes or corrupt the local DB. Production should use a real SQLite driver, PostgreSQL, or a write queue with locking.

14. Response IDs are short random strings

   Evidence:
   - `server/app.js:76` creates IDs from `Math.random().toString(36).substring(2, 10)`.

   Impact: collisions are unlikely at tiny scale, but this is not durable enough for a public API. Use `crypto.randomUUID()` or another cryptographically strong ID.

### Low Severity / Cleanup

15. No automated test or lint scripts

   Evidence:
   - `package.json` only defines `start` and `dev`.
   - `npm.cmd test` failed with `Missing script: "test"`.

   Impact: there is no one-command validation path for regressions in API behavior, frontend scripting, quiz data schema, or pipeline modules.

16. README setup instructions are stale

   Evidence:
   - `README.md:65` tells users to install `google-generativeai`.
   - `requirements.txt:2` uses `google-genai>=1.0.0`.
   - `README.md:70` says to edit `config.json`, but the tracked file is `example.config.json`; `config.json` is intentionally ignored by `.gitignore:5`.

   Impact: fresh setup is ambiguous. Document copying `example.config.json` to `config.json`, then editing keys, and update the dependency name.

17. Git/global-ignore warning appears during git commands

   Evidence:
   - `git status --short` prints `warning: unable to access 'C:\\Users\\ameli/.config/git/ignore': Permission denied`.

   Impact: repo commands still work, but the local Git environment is noisy and may hide useful status output in scripts.

18. `data/` is ignored but local app behavior depends on it

   Evidence:
   - `.gitignore:3` ignores `/data`.
   - `server/app.js:82` and `server/app.js:101` read quizzes from `data/quizzes`.
   - `data/` is present locally but not tracked by Git.

   Impact: a fresh clone will not include the sample quizzes/images described by `README.md`, unless they are generated or supplied separately.

## Verification Notes

Commands run:

```powershell
node --check server\app.js
.\.venv\Scripts\python.exe -m compileall pipeline generate_quiz.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe pipeline\run_pipeline.py --list
.\.venv\Scripts\python.exe pipeline\run_pipeline.py --type trivia --category history --topic Test --skip-images
npm.cmd test
```

Results:

- `node --check server\app.js` passed.
- Python compile passed using the local virtualenv.
- `pip check` reported no broken Python requirements.
- `pipeline/run_pipeline.py --list` worked after the existing local change in `pipeline/run_pipeline.py`.
- Pipeline generation failed before quiz generation because `pytrends` tried to contact Google Trends during construction.
- `npm.cmd test` failed because no test script exists.
- Plain `python` and `py` are not available globally in this shell; the repo-local `.venv\Scripts\python.exe` works.
- PowerShell blocks `npm.ps1`; `npm.cmd` works.

## Pre-existing Working Tree Notes

- `pipeline/run_pipeline.py` was already modified before this audit. I did not revert it.
- `config.json` exists locally but is ignored by Git, so I did not include or inspect secret values.
