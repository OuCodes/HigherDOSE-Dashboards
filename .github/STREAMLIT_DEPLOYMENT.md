# 🚨 Streamlit Deployment Quick Reference

## The #1 Rule

**Streamlit Cloud deploys from the `dashboards` remote, NOT `origin`!**

```bash
git push dashboards main    # ← This deploys to Streamlit Cloud
git push origin main        # ← This does NOT deploy to Streamlit Cloud
```

---

## Files That Need `dashboards` Remote

Any Python file that runs as a web app:
- ✅ `q1_growth_forecast_app.py`
- ✅ `q4_tracker_streamlit.py`
- ✅ `streamlit_app.py`
- ✅ Any other `*_app.py` or dashboard files

---

## Standard Workflow

```bash
# 1. Edit the dashboard file
vim q1_growth_forecast_app.py

# 2. Test locally
streamlit run q1_growth_forecast_app.py

# 3. Commit
git add q1_growth_forecast_app.py
git commit -m "Fix: your description"

# 4. Push to BOTH remotes
git push origin main       # Keep main repo synced
git push dashboards main   # Deploy to Streamlit Cloud ← CRITICAL!

# 5. Wait 1-2 min for Streamlit Cloud auto-deploy
```

---

## Common Mistake

❌ **WRONG:**
```bash
git push origin main
# Then wonder why Streamlit Cloud still shows the error
```

✅ **CORRECT:**
```bash
git push dashboards main
# Streamlit Cloud will auto-deploy in ~1-2 minutes
```

---

## Quick Check

```bash
# See which remotes you have
git remote -v

# You should see both:
# origin      → oucodes/HigherDOSE
# dashboards  → OuCodes/higherdose-dashboards
```

---

Read [DEPLOYMENT.md](../DEPLOYMENT.md) for full details.
