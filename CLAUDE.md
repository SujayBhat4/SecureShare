# Project rules for SecureShare

## Source of truth
- `BUILD_SECURESHARE.md` is the build specification. Follow it exactly and build the phases in order.
- `docs/blueprint.md` is the background design document. If the two disagree, `BUILD_SECURESHARE.md` wins.
- Do not add features that are not in those files.

## Who this is for
- I am a student who must explain every line of this code in interviews (PwC campus drive).
- Keep code simple and readable. No clever tricks, no extra abstractions, no unnecessary libraries.
- After finishing, write `EXPLAINED.md` as described in `BUILD_SECURESHARE.md`.

## Environment
- Windows. Use Python 3.12 only. Create the venv with `py -3.12 -m venv venv`.
- AWS region is `ap-southeast-2` (Sydney), not `ap-south-1`. Read it from `.env`.
- Local database is PostgreSQL in Docker (`docker compose`).
- The `.env` file is in the project root. Read settings from it.

## Safety rules
- Never put secrets in code. Never print, log, echo or commit values from `.env`.
- Never commit `.env`. Check `git status` before every commit.
- Only touch the one S3 bucket named in `.env`. Do not create, change or delete any other AWS resource, and do not change bucket policies or permissions.
- If an AWS call fails with an access or region error, stop and tell me exactly what failed.
- Ask me before installing any library that is not listed in `BUILD_SECURESHARE.md`.

## Working style
- Build in the phases from `BUILD_SECURESHARE.md`. Run each phase's check before starting the next.
- Commit after each phase with a clear message, for example `Phase 3: file upload to S3`.
- Add a short comment above each function saying what it does and why. Inline comments only where the logic is not obvious.
- When something is ambiguous, choose the simplest option and note the choice in `EXPLAINED.md`.
