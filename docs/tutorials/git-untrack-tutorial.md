# How to Remove Directories from Git Tracking

## Problem: Git Won't Ignore Already-Tracked Files

If you add a directory to `.gitignore` but git is still tracking changes to files in that directory, it's because **`.gitignore` only affects untracked files**. Once files are tracked by git, adding them to `.gitignore` has no effect.

## Solution: Untrack Files While Keeping Them on Disk

Follow these steps to remove files/directories from git tracking while preserving them locally:

### Step 1: Check What's Being Tracked

First, verify which files git is currently tracking in the target directory:

```bash
git ls-files path/to/directory
```

Example for mail/archive:
```bash
git ls-files src/higherdose/mail/archive
```

### Step 2: Remove from Git Tracking (Keep Local Files)

Use `git rm --cached` to remove files from git's index while keeping them on your filesystem:

```bash
# Remove a single file
git rm --cached path/to/file

# Remove an entire directory recursively
git rm -r --cached path/to/directory
```

**Key Commands for mail/archive:**
```bash
git rm -r --cached src/higherdose/mail/archive
```

⚠️ **Important**: The `--cached` flag is crucial - it removes files from git tracking but keeps them on disk.

### Step 3: Update .gitignore

Add the appropriate ignore pattern to `.gitignore`:

```gitignore
# To ignore specific path
src/higherdose/mail/archive/

# To ignore directory anywhere in repo (recommended)
**/mail/archive/
```

The `**/mail/archive/` pattern means:
- `**` = match any number of directories at any depth
- `/mail/archive/` = followed by the specific path
- Trailing `/` = match directories and their contents

### Step 4: Verify the Ignore is Working

Test that git now ignores the files:

```bash
git check-ignore path/to/file
```

Example:
```bash
git check-ignore src/higherdose/mail/archive/somefile.md
```

If the command outputs the file path, git is successfully ignoring it.

### Step 5: Commit the Changes

The `git rm --cached` command stages the file deletions. Commit these changes:

```bash
git add .gitignore
git commit -m "Remove mail/archive from git tracking and add to .gitignore"
```

## Complete Example Workflow

```bash
# 1. Check what's tracked
git ls-files src/higherdose/mail/archive

# 2. Remove from tracking (keep local files)
git rm -r --cached src/higherdose/mail/archive

# 3. Add to .gitignore (edit the file to add **/mail/archive/)
echo "**/mail/archive/" >> .gitignore

# 4. Verify ignore is working
git check-ignore src/higherdose/mail/archive/somefile.md

# 5. Commit the changes
git add .gitignore
git commit -m "Remove mail/archive from git tracking"
```

## Common Mistakes to Avoid

1. **Don't use `git rm` without `--cached`** - This will delete files from your filesystem
2. **Don't forget to update `.gitignore`** - Files will be tracked again if you don't ignore them
3. **Don't use relative paths in `.gitignore`** - Use patterns like `**/directory/` for flexibility

## Verification Commands

After completing the process, verify everything worked:

```bash
# Should show no output (files not tracked)
git ls-files src/higherdose/mail/archive

# Should list the file path (git is ignoring it)
git check-ignore src/higherdose/mail/archive/anyfile.md

# Should show files still exist locally
ls src/higherdose/mail/archive/
```

## What This Accomplishes

- ✅ Files remain on your local filesystem
- ✅ Git stops tracking changes to these files
- ✅ Files won't appear in `git status` output
- ✅ Files won't be included in future commits
- ✅ Other developers won't see these files when they clone/pull 