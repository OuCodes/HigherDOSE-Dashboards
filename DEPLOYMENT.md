# 🚀 Deployment Guide - HigherDOSE Repository

## ⚠️ IMPORTANT: Two Repository Setup

This repository has **TWO git remotes** that serve different purposes:

```bash
$ git remote -v

dashboards    git@github.com:OuCodes/higherdose-dashboards.git     # ← STREAMLIT CLOUD USES THIS
origin        git@oucodes.github.com:oucodes/HigherDOSE.git        # ← Main research repo
```

---

## 📍 Which Repository to Use

### Use `origin` (HigherDOSE) for:
- ✅ Data analysis scripts in `scripts/`
- ✅ Reports in `data/reports/`
- ✅ New data exports in `data/ads/`
- ✅ Research notebooks
- ✅ Source code in `src/growthkit/`
- ✅ Configuration changes
- ✅ Documentation updates

**Push command:**
```bash
git push origin main
```

### Use `dashboards` (higherdose-dashboards) for:
- ✅ **Streamlit apps** (anything that needs to run on Streamlit Cloud)
- ✅ `streamlit_app.py`
- ✅ `q1_growth_forecast_app.py`
- ✅ `q4_tracker_streamlit.py`
- ✅ Any `.py` file that runs as a web dashboard
- ✅ Changes to `requirements.txt` if needed for Streamlit
- ✅ Changes to `.streamlit/config.toml` or other Streamlit settings

**Push command:**
```bash
git push dashboards main
```

---

## 🎯 Quick Decision Tree

**Ask yourself:** "Will this change affect a Streamlit dashboard?"

- **YES** → Push to `dashboards` remote
- **NO** → Push to `origin` remote
- **BOTH** → Push to both remotes

---

## 🔄 Standard Deployment Workflow

### For Streamlit Dashboard Changes:

```bash
# 1. Make your changes to the dashboard file
vim q1_growth_forecast_app.py

# 2. Stage and commit
git add q1_growth_forecast_app.py
git commit -m "Fix: description of what you fixed"

# 3. Push to BOTH remotes (recommended)
git push origin main       # Keep main repo in sync
git push dashboards main   # Deploy to Streamlit Cloud ← REQUIRED for Streamlit!

# 4. Wait 1-2 minutes for Streamlit Cloud to auto-deploy
# Or manually reboot from Streamlit Cloud dashboard
```

### For Analysis/Research Work:

```bash
# 1. Make your changes
vim scripts/analyze_something.py

# 2. Stage and commit  
git add scripts/analyze_something.py
git commit -m "Add: new analysis script"

# 3. Push to origin only
git push origin main
```

---

## 🐛 Common Issues

### Issue 1: "I fixed the Streamlit error but it's still showing!"

**Problem:** You pushed to `origin` but not `dashboards`

**Solution:**
```bash
git push dashboards main  # ← This is what Streamlit Cloud needs!
```

### Issue 2: "Which branch is Streamlit Cloud running?"

**Answer:** Streamlit Cloud runs from:
- **Repository:** `OuCodes/higherdose-dashboards`
- **Branch:** `main`
- **Remote:** `dashboards`

### Issue 3: "How do I check which remote I last pushed to?"

```bash
# See recent pushes
git log --oneline --all --graph --decorate -10

# Or check status
git status
git remote show origin
git remote show dashboards
```

---

## 📊 Current Streamlit Apps

These files run on Streamlit Cloud and **MUST** be pushed to `dashboards` remote:

1. **Q1 Growth Forecast Dashboard**
   - File: `q1_growth_forecast_app.py`
   - URL: [Your Streamlit Cloud URL]
   - Remote: `dashboards`

2. **Q4 Tracker Dashboard**
   - File: `q4_tracker_streamlit.py`
   - URL: [Your Streamlit Cloud URL]
   - Remote: `dashboards`

3. **Main Streamlit App**
   - File: `streamlit_app.py`
   - URL: [Your Streamlit Cloud URL]
   - Remote: `dashboards`

---

## 🔍 Verify Before Pushing

Before pushing to `dashboards`, run a quick check:

```bash
# Check current branch
git branch

# Check what you're about to push
git diff origin/main..HEAD

# Check remote status
git remote -v
```

---

## 💡 Pro Tips

1. **Always commit first, then push to both remotes:**
   ```bash
   git add .
   git commit -m "Your message"
   git push origin main && git push dashboards main
   ```

2. **Create an alias to push to both at once:**
   ```bash
   # Add to ~/.gitconfig or ~/.zshrc
   alias git-push-both='git push origin main && git push dashboards main'
   
   # Then use:
   git-push-both
   ```

3. **If you're working on a Streamlit app, ALWAYS test locally first:**
   ```bash
   streamlit run q1_growth_forecast_app.py
   ```

4. **Check Streamlit Cloud logs if deployment fails:**
   - Go to Streamlit Cloud dashboard
   - Click on your app
   - View logs for errors

---

## 🆘 Emergency Recovery

If you pushed to the wrong remote and need to fix:

```bash
# 1. Make sure your local commit is good
git log -1

# 2. Force push to the correct remote
git push dashboards main --force-with-lease  # Use with caution!
```

---

## 📝 Checklist for Streamlit Dashboard Fixes

- [ ] Made changes to dashboard file locally
- [ ] Tested locally with `streamlit run <file>.py`
- [ ] Committed changes with clear message
- [ ] Pushed to `dashboards` remote (not just `origin`!)
- [ ] Waited 1-2 minutes for auto-deploy
- [ ] Checked Streamlit Cloud logs if needed
- [ ] Verified fix is live on Streamlit Cloud URL

---

## 🎓 Remember

**Golden Rule:** If it shows up on a web browser via Streamlit Cloud, it needs to go to the `dashboards` remote!

**Last Updated:** December 23, 2025
