# CSV File Management Strategy

## Problem
The repository has many CSV files ranging from small (few KB) to very large (90MB+). Large files cause issues:
- Slow cloning/fetching
- Repository bloat
- GitHub's file size limits
- Accidental commits of huge files

## Current Situation
- 47 CSV files currently tracked in git
- Sizes range from <1KB to 90MB
- Previously had blanket `*.csv` in `.gitignore` but this blocked all CSVs

## Solution: Size-Based Pre-Commit Hook

### Implementation
1. **Pre-commit hook** (`.githooks/pre-commit`) blocks CSV files >10MB
2. **Allows smaller CSVs** for working data and analysis
3. **Configurable threshold** - easy to adjust the 10MB limit

### File Size Thresholds Recommended
- **< 1MB**: Always allow (small working datasets)
- **1MB - 10MB**: Allow with caution (medium datasets)
- **> 10MB**: Block by default (requires conscious decision)

### Benefits
- ✅ Prevents accidental large file commits
- ✅ Preserves access to smaller working datasets
- ✅ Team member gets clear error message with suggestions
- ✅ Can override with `--no-verify` if needed
- ✅ No external dependencies required

## Alternative Approaches

### Option A: Git LFS (Large File Storage)
```bash
# Setup (if you want to use LFS instead)
git lfs install
git lfs track "*.csv"
git add .gitattributes
```

**Pros:**
- Files are tracked but stored externally
- Faster clones
- GitHub supports it

**Cons:**
- Adds complexity
- Costs money on GitHub (bandwidth/storage)
- All team members need LFS setup
- Not great for frequently changing data files

### Option B: Specific File Patterns
Add to `.gitignore`:
```
# Block specific large file patterns
**/mtd-sales_data-*.csv
**/ytd-*-sales_data-*.csv
data/ads/h1-report/northbeam-*.csv
```

**Pros:**
- Targeted approach
- Simple to understand

**Cons:**
- Requires knowing patterns in advance
- Easy to miss new large file types

### Option C: Directory-Based Strategy
```
# In .gitignore
data/ads/large/
data/ads/archive/
```

**Pros:**
- Clear separation
- Team knows where to put large files

**Cons:**
- Requires reorganizing existing files
- Relies on team discipline

## Current Implementation Details

### Pre-commit Hook
- Checks any CSV files being committed
- 10MB size limit (configurable)
- Provides helpful error messages with alternatives
- Can be bypassed with `git commit --no-verify`

### Setup Commands
```bash
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
```

### Testing the Hook
```bash
# Create a large dummy file to test
dd if=/dev/zero of=test-large.csv bs=1m count=15
git add test-large.csv
git commit -m "test"  # Should be blocked
rm test-large.csv
```

## Recommendations

1. **Use the pre-commit hook approach** (current implementation)
2. **Set team guidelines**:
   - Raw exports >10MB go to external storage (Google Drive, S3, etc.)
   - Processed/filtered data <10MB can be committed
   - Use compression for medium-sized files when possible
3. **Regular cleanup**: Review large tracked files quarterly
4. **Consider LFS** only if you need to version large files frequently

## Migration Strategy

For existing large files already tracked:
```bash
# See current large files
git ls-files "*.csv" | while read file; do
    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
        if [ "$size" -gt 10485760 ]; then
            echo "$file ($(numfmt --to=iec --suffix=B $size))"
        fi
    fi
done

# Option 1: Remove from history (careful!)
git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch path/to/large/file.csv' --prune-empty --tag-name-filter cat -- --all

# Option 2: Move to LFS
git lfs migrate import --include="*.csv" --include-ref=refs/heads/main

# Option 3: Accept current state, prevent future large files
# (This is what we're doing - least disruptive)
```