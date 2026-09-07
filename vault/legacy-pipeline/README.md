# Legacy Pipeline Vault

This directory preserves retired Eagle Eyes pipeline/configuration artifacts for historical reference.

## Rules

- Reference-only: do not execute archived scripts against the current V13 repository.
- Archived files must not be wired into GitHub Actions, Railway, Vercel, npm scripts, or runtime startup.
- Never store secret values here. Keep tokens, passwords, API keys, and signing material in encrypted platform secret/environment stores.
- The active source of truth remains the current root `package.json` and `.github/workflows/eagle-eyes-live-cicd.yml`.

`fix-pipeline.js.disabled` is the retired automated configuration script discussed during pipeline repair. It is intentionally disabled because it would overwrite newer V13 package/start/test configuration and create a duplicate deployment workflow.
