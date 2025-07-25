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

Example for mail/exports:
```bash
git ls-files data/mail/exports
```

### Step 2: Remove from Git Tracking (Keep Local Files)

Use `git rm --cached` to remove files from git's index while keeping them on your filesystem:

```bash
# Remove a single file
git rm --cached path/to/file

# Remove an entire directory recursively
git rm -r --cached path/to/directory
```

**Key Commands for mail/exports:**
```bash
git rm -r --cached data/mail/exports
```

⚠️ **Important**: The `--cached` flag is crucial - it removes files from git tracking but keeps them on disk.

### Step 3: Update .gitignore

Add the appropriate ignore pattern to `.gitignore`:

```gitignore
# To ignore specific path
data/mail/exports/

# To ignore directory anywhere in repo (recommended)
**/mail/exports/
```

The `**/mail/exports/` pattern means:
- `**` = match any number of directories at any depth
- `/mail/exports/` = followed by the specific path
- Trailing `/` = match directories and their contents

### Step 4: Verify the Ignore is Working

Test that git now ignores the files:

```bash
git check-ignore path/to/file
```

Example:
```bash
git check-ignore data/mail/exports/somefile.md
```

If the command outputs the file path, git is successfully ignoring it.

### Step 5: Commit the Changes

The `git rm --cached` command stages the file deletions. Commit these changes:

```bash
git add .gitignore
git commit -m "Remove mail/exports from git tracking and add to .gitignore"
```

## Complete Example Workflow

```bash
# 1. Check what's tracked
git ls-files data/mail/exports

# 2. Remove from tracking (keep local files)
git rm -r --cached data/mail/exports

# 3. Add to .gitignore (edit the file to add **/mail/exports/)
echo "**/mail/exports/" >> .gitignore

# 4. Verify ignore is working
git check-ignore data/mail/exports/somefile.md

# 5. Commit the changes
git add .gitignore
git commit -m "Remove mail/exports from git tracking"
```

## Common Mistakes to Avoid

1. **Don't use `git rm` without `--cached`** - This will delete files from your filesystem
2. **Don't forget to update `.gitignore`** - Files will be tracked again if you don't ignore them
3. **Don't use relative paths in `.gitignore`** - Use patterns like `**/directory/` for flexibility

## Verification Commands

After completing the process, verify everything worked:

```bash
# Should show no output (files not tracked)
git ls-files data/mail/exports

# Should list the file path (git is ignoring it)
git check-ignore data/mail/exports/anyfile.md

# Should show files still exist locally
ls data/mail/exports/
```

## What This Accomplishes

- ✅ Files remain on your local filesystem
- ✅ Git stops tracking changes to these files
- ✅ Files won't appear in `git status` output
- ✅ Files won't be included in future commits
- ✅ Other developers won't see these files when they clone/pull 

Here’s the quick-fix checklist distilled from `docs/tutorials/git-untrack-tutorial.md` and adapted to your archive problem.

1. Verify what’s still tracked  
   (replace the path if your exports live somewhere else):
   ```bash
   git ls-files data/mail/exports
   ```

2. Stop tracking the directory but keep the files on disk:  
   ```bash
   git rm -r --cached data/mail/exports
   ```

3. Make sure the ignore rule is in `.gitignore`  
   (you already have this line, but double-check in case of typos):
   ```
   **/mail/exports/
   ```

4. Commit the changes:
   ```bash
   git add .gitignore
   git commit -m "Remove mail/exports from git tracking"
   ```

5. Confirm everything worked:
   ```bash
   # Should print nothing
   git ls-files data/mail/exports

   # Should print the path (means git is ignoring it)
   git check-ignore data/mail/exports/anyfile.md
   ```

If `git ls-files` in step 1 already shows nothing, tracking has been removed—any remaining issue is usually a mismatched ignore pattern (extra spaces, missing slash, etc.). Fix the pattern, then clear the index again with steps 2-4. 