# Adding a tool to the Pi backup and restore (Claude Code, agy, ...)

Goal: a rebuilt Pi gets the tool installed, configured and signed in with the same steps for every tool.
Audit an existing tool first (`grep -n -i <tool> raspberry-pi/{save.sh,restore.sh,README.md,MULTI-PI.md} raspberry-pi/backup/includes.txt raspberry-pi/snapshot/Brewfile`) and compare it against Claude Code, the reference case.

## The three places (split by sensitivity: the snapshot is PUBLIC git, restic is encrypted)
1. **Install**: `snapshot/Brewfile` (casks/formulae), `uv-tools.txt`, `npm-global.txt` are written by `save.sh`; restore.sh's brew/uv/npm steps already install from them. Find how the tool was installed (`brew list --cask --versions`, `readlink -f $(which tool)`) and just re-run `save.sh`; do not hand-edit the Brewfile.
2. **Non-secret config** (settings.json with model/status line/permissions, status line script, CLAUDE.md-style notes): add the path, relative to `$HOME`, to the `dotfiles=(...)` array in `save.sh`; restore.sh's dotfiles step copies it back. A script that lives outside any repo (e.g. `~/dev/statusline.sh`) belongs here too, or it is lost.
3. **Secrets and data** (OAuth token, MCP configs that may hold tokens, conversations, memory, prompt history): `backup/includes.txt`, one `<group> <path>` per line (`signins` for tokens/config, `data` for the rest). List data paths explicitly rather than the whole tool dir, so downloaded runtimes (`bin/`), `log/`, `cache/`, `updater/` stay out. `*.db` files under an include are staged with SQLite's backup API automatically.

Then document it: the sign-in step in `restore.sh` (both message blocks that mention `claude`), `README.md` (sign-in list), and the `MULTI-PI.md` interface table (the contract) in the same commit.

## Verify without touching Drive or lab-chromium
- `bash -n save.sh restore.sh`; `pi-backup list | grep <tool>` shows every resolved include.
- Throwaway repo in a fresh unique scratch dir: `restic init -r $sc/repo --password-file $sc/pw`; `sed "s#^~/#$HOME/#" backup/excludes.txt > $sc/ex.txt`; `pi-backup list | grep <tool> | cut -f2 > $sc/paths.txt`; `restic backup -r ... --exclude-file $sc/ex.txt --files-from $sc/paths.txt`; check `restic ls` has the token/settings and lacks `bin/`, `log/`; `restic restore ... --include <path>` and `cmp` the token against the original. This skips staging, so the browser is not restarted.
- `brew bundle check --file=snapshot/Brewfile`.

## Commit hygiene
`save.sh` rebuilds the WHOLE snapshot, so it also pulls in unrelated drift (other dotfiles, skills, npm list). After running it, `git status`, then `git checkout -- <unrelated snapshot paths>` so the commit holds only the tool's change; say what drift was left for the user's next save. A new snapshot file for the tool shows as untracked: `git add` it explicitly and confirm with `git show --stat`.
