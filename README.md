# HigherDOSE Growth Report Analysis

A Python-based analysis tool for HigherDOSE's weekly and monthly growth reports, providing insights into sales performance, channel effectiveness, and campaign optimization.

## Installation

> **Requirement**: Python **3.10** or newer must already be installed and available on your `PATH`.
>
> Check with:
> ```bash
> python --version   # or python3 --version on macOS/Linux
> ```

### 1. Create & activate a virtual environment

Create a dedicated environment (named `hdose`) inside a folder called `venv`:

```bash
# macOS / Linux
python3 -m venv --prompt hdose venv
source venv/bin/activate
```

```cmd
:: Windows Command Prompt
python -m venv --prompt hdose venv
venv\Scripts\activate.bat
```

### 2. Upgrade `pip` (recommended)
```bash
pip install --upgrade pip wheel setuptools
```

### 3. Install project dependencies
```bash
pip install pandas numpy
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install markdownify
```

### 4. Verify the environment
```bash
python -c "import pandas, numpy, sys; print(f'✅ Environment ready — Python {sys.version.split()[0]}')"
```

### Running the Analysis

After installation, you can run the analysis scripts:

#### Weekly Report Analysis:
```bash
# macOS
python3 report_analysis_weekly.py

# Windows  
python report_analysis_weekly.py
```

#### Monthly Report Analysis:
```bash
# macOS
python3 report_analysis_monthly.py

# Windows
python report_analysis_monthly.py
```

### Troubleshooting

#### Common Issues:

**macOS:**
- If you get "command not found" errors, try using `python` instead of `python3`
- If pip installation fails, try: `python3 -m pip install pandas numpy`

**Windows:**
- If Python is not recognized, ensure it was added to PATH during installation
- If you get permission errors, try running Command Prompt as Administrator

**Both platforms:**
- If you encounter SSL certificate errors, try: `pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org pandas numpy`
