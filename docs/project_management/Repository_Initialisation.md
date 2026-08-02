# F2S Repository Initialisation

## Assumptions

- Run commands from the directory that should become the F2S repository root.
- Git 2.28 or newer is installed.
- Replace `YOUR_GITHUB_USERNAME` before running the remote command.
- The GitHub repository `F2S` already exists and is empty.
- Review the staged files before the first commit. Do not commit secrets, personal financial data, generated dependencies, or unrelated content accidentally.

## PowerShell commands

Run each command in order:

```powershell
Set-Location -LiteralPath 'C:\Users\teint\Projects\F2S'
git --version
git status
git init -b main
git status --short
git add -- .
git diff --cached --stat
git diff --cached
git commit -m "docs: establish F2S phase 0 foundation"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/F2S.git
git remote -v
git push -u origin main
```

If `git status` before `git init` reports an existing valid worktree, stop and do not reinitialise it. Continue from the review and staging commands only after confirming the current branch and remote:

```powershell
git branch --show-current
git remote -v
git status --short
```

## POSIX shell commands

For a clone of the same files on Linux, macOS, or WSL:

```bash
cd /absolute/path/to/F2S
git --version
git status
git init -b main
git status --short
git add -- .
git diff --cached --stat
git diff --cached
git commit -m "docs: establish F2S phase 0 foundation"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/F2S.git
git remote -v
git push -u origin main
```

## Optional GitHub CLI repository creation

Use this instead of manually creating the empty GitHub repository and running `git remote add origin`:

```powershell
gh auth status
gh repo create F2S --private --source . --remote origin
git push -u origin main
```

Choose public visibility only after confirming that the repository contains no private family information or secrets:

```powershell
gh repo create F2S --public --source . --remote origin
git push -u origin main
```

Do not run both `git remote add origin ...` and `gh repo create ... --remote origin` for the same repository.

## Verification commands

```powershell
git status
git log -1 --oneline
git branch --show-current
git remote -v
git ls-files
```

Expected results:

- the current branch is `main`;
- the initial commit message is `docs: establish F2S phase 0 foundation`;
- `origin` points to the intended F2S repository;
- the worktree is clean after the commit; and
- no `.env`, credentials, personal financial data, dependency directory, or local database is tracked.

## GitHub project setup

After the first push:

1. Create the 12 milestones exactly as defined in [GitHub Milestones](GitHub_Milestones.md).
2. Create the first issues from [First 20 GitHub Issues](First_20_GitHub_Issues.md).
3. Apply phase, type, security, and priority labels consistently.
4. Add branch protection only after the CI foundation exists and required checks are stable.
5. Work on one issue at a time and stop when its acceptance criteria are met.
