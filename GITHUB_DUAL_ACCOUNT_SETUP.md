# Dual GitHub Account Setup (abc + abc-work)

This document describes how to use two GitHub accounts on the same machine:
- **abc** (personal) — for repos under `~/yourProject/`
- **abc-work** (work) — for all other repos

---

## Prerequisites

- Two GitHub accounts: `abc` and `abc-work`
- Two SSH keys:
  - `~/.ssh/id_ed25519_personal` — for personal (abc)
  - `~/.ssh/id_rsa` — for work (abc-work)
- Each key added to the correct GitHub account

---

## Step 1: Create the personal Git config file

Create `~/.gitconfig-personal`:

```ini
[user]
    name = abc
    email = personal.email@gmail.com
    signingkey = ""

[commit]
    gpgsign = false

[core]
    sshCommand = "ssh -i ~/.ssh/id_ed25519_personal -o IdentitiesOnly=yes -o IdentityFile=~/.ssh/id_ed25519_personal"
```

**Note:** The `IdentityFile` override ensures the personal key is used even when `~/.ssh/config` defaults `github.com` to the work key.

---

## Step 2: Add includeIf to main Git config

Add this to `~/.gitconfig` (typically at the end):

```ini
[includeIf "gitdir:i:/Users/abc/yourProject/"]
    path = /Users/abc/.gitconfig-personal
```

- `gitdir:i:` — case-insensitive path match
- Path must be absolute and include trailing `/`
- Adjust the path if your username or folder name differs

---

## Step 3: Add personal GitHub host to SSH config

Add this to `~/.ssh/config` (keep your existing `Host github.com` block for work):

```
Host github.com-personal
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_personal
    IdentitiesOnly yes
```

---

## Step 4: Use the personal host in remote URLs

For any repo under `~/youProject/`, set the remote to use `github.com-personal`:

```bash
# For your own repos
git remote set-url origin git@github.com-personal:abc/REPO_NAME.git


To verify:

```bash
git remote -v
```

---

## Verification

From a repo under `~/youProject/`:

```bash
# Should show personal account and email
git config user.name
git config user.email

# Should show the personal SSH command
git config core.sshCommand

# Test push (replace with your branch name)
git push origin main
```

---

## Troubleshooting

| Issue | Check                                                                                                      |
|-------|------------------------------------------------------------------------------------------------------------|
| Wrong user/email | `includeIf` path may not match. Ensure repo is under `~/yourProject/` and path in `.gitconfig` is correct. |
| Wrong key used | Ensure remote URL uses `github.com-personal`, not `github.com`.                                            |
| Push denied | Confirm the correct SSH key is added to the GitHub account that owns the repo.                             |
| `includeIf` not working | Use absolute paths; ensure no trailing slash typo; run `git config --list --show-origin` from the repo.    |

---

## Summary

| Location         | Account | SSH key             | Remote host |
|------------------|---------|---------------------|-------------|
| `~/yourProject/` | abc | id_ed25519_personal | `github.com-personal` |
| Everywhere else  | abc-work | id_rsa              | `github.com` |
