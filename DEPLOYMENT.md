# Deployment Guide

## Setting Up the Public Repository on GitHub

1. Go to [GitHub](https://github.com) and create a new repository
   - Name: `HigherDOSE-Dashboards` (or any name you prefer)
   - ✅ Make it **PUBLIC**
   - Don't initialize with README (we already have one)

2. After creating the repo, run these commands:

```bash
cd /Users/jourdansmith/code/research/HigherDOSE-Dashboards
git remote add origin git@github.com:OuCodes/HigherDOSE-Dashboards.git
git push -u origin main
```

## Deploying on Streamlit Cloud

### For Each Dashboard:

1. Go to [share.streamlit.io](https://share.streamlit.io/)
2. Click "New app"
3. Fill in:
   - **Repository:** `OuCodes/HigherDOSE-Dashboards`
   - **Branch:** `main`
   - **Main file path:** Choose one:
     - `december_comparison_app.py`
     - `streamlit_app.py`
     - `november_insights_app.py`

4. Click "Deploy"

### Handling Data Files

Since data files aren't in the public repo (for privacy), you have two options:

#### Option A: Upload via GitHub (if data can be public)
```bash
cd /Users/jourdansmith/code/research/HigherDOSE-Dashboards
# Copy specific data files you want to make public
cp -r /path/to/data/files data/
git add data/
git commit -m "Add data files"
git push
```

#### Option B: Use Streamlit Secrets (recommended for sensitive data)
1. In Streamlit Cloud app settings → "Secrets"
2. Add data file URLs or connection strings
3. Modify apps to read from secrets

#### Option C: Mount from Google Drive/Dropbox
- Use Streamlit file uploader
- Or integrate with cloud storage API

## App URLs

After deployment, your apps will be available at:
- `https://yourapp-december.streamlit.app`
- `https://yourapp-bfcm.streamlit.app`
- `https://yourapp-november.streamlit.app`

## Updating Apps

To update any dashboard:
```bash
cd /Users/jourdansmith/code/research/HigherDOSE-Dashboards
# Make your changes
git add .
git commit -m "Update dashboard"
git push
```

Streamlit Cloud will automatically redeploy!
