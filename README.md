# Daily Python / Django Fresher Job Alerts

Every morning at about 7:45 AM IST, this finds new **fresher-friendly Python and Django jobs** in **Bengaluru, Hyderabad and remote (open to India)**, and sends them to your **Telegram** and/or **Gmail**.

It runs free on GitHub Actions. Your laptop can be off. No Claude, no subscriptions.

## What it does

1. Pulls jobs from Adzuna (India), Jooble (India), Remotive (remote) and Himalayas (remote).
2. Keeps only **Python Developer** and **Django / full stack developer** titles. Data science, ML, QA/testing, DevOps, trainer and similar roles are dropped even if they mention Python.
3. Drops senior roles (Senior, Lead, Manager, Architect…) and anything asking for 2+ years.
4. Drops expired jobs (closing date passed) and anything posted more than 14 days ago.
5. Splits the rest into two groups, newest first:
   - **Fresher-friendly**: says fresher, junior, trainee, graduate, 0–1 years, etc.
   - **Experience not stated**: worth a quick look before applying.
6. Shows **salary**, **posting date** and **closing date** for each job when the site provides them. Adzuna salaries marked "(est.)" are Adzuna's own estimate, not the employer's number.
7. Skips anything it already sent you before, even if the same job appears on two sites.
8. Sends the digest.

## One-time setup (about 15 minutes)

### Step 1: Put the project on GitHub

1. Go to github.com → **New repository** → name it `daily-job-alerts` → **Private** → Create.
2. Click **uploading an existing file** and upload everything in this folder: `jobs.py`, `requirements.txt`, `seen_jobs.json`, `README.md`.
3. The workflow file has to sit in a folder path. Click **Add file → Create new file**, type the name exactly as `.github/workflows/daily-jobs.yml` (GitHub creates the folders as you type the slashes), then paste in the contents of `daily-jobs.yml` and commit.

### Step 2: Get free job API keys

**Adzuna** (main source for Bengaluru and Hyderabad)
1. Sign up at developer.adzuna.com.
2. Open your dashboard and copy the **Application ID** and **Application Key**.

**Jooble** (extra Indian listings, optional but recommended)
1. Go to jooble.org/api/about and fill the short form.
2. They email you an API key.

Remotive and Himalayas need no keys.

### Step 3: Set up Telegram (recommended)

1. In Telegram, search **@BotFather** → send `/newbot` → pick a name and username. It gives you a **bot token**.
2. Open your new bot and send it any message, like `hi`.
3. In a browser, open this link with your token pasted in:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Find `"chat":{"id":` followed by a number. That number is your **chat ID**.

### Step 4: Set up Gmail (optional)

1. Turn on 2-Step Verification in your Google account.
2. Go to myaccount.google.com/apppasswords → create an app password named "job alerts".
3. Copy the 16-character password. Use this, not your normal password.

### Step 5: Add the secrets to GitHub

In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add each one you have:

| Secret name | What to paste |
|---|---|
| `ADZUNA_APP_ID` | Adzuna Application ID |
| `ADZUNA_APP_KEY` | Adzuna Application Key |
| `JOOBLE_API_KEY` | Jooble key |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_CHAT_ID` | The number from Step 3 |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | The 16-character app password |
| `EMAIL_TO` | Optional: a different address to receive the email |

Skip any you don't use. A missing source or delivery channel is just skipped.

### Step 6: Test it

1. Go to the **Actions** tab → allow workflows if asked.
2. Click **Daily Python/Django job alerts** → **Run workflow**.
3. Within a minute or two you should get your first digest.

After that it runs by itself every morning.

## Changing things later

All settings are at the top of `jobs.py`. Edit on GitHub with the pencil icon:

- **Search terms**: `SEARCH_TERMS`
- **Which job titles count**: `TITLE_TECH`, `TITLE_ROLE`, `TITLE_EXCLUDE`
- **How old a job can be**: `MAX_AGE_DAYS`
- **Cities**: `CITIES` and `CITY_ALIASES`
- **How strict the fresher filter is**: `SENIOR_TITLE_WORDS` and `FRESHER_WORDS`
- **Run time**: the `cron` line in the workflow file (it's in UTC; IST is UTC + 5:30)

## Good to know

- GitHub may pause scheduled workflows in a repo with no activity for 60 days. The daily save of `seen_jobs.json` counts as activity, so this normally keeps it alive. If it ever stops, just click Run workflow once.
- The filter reads job text, so it isn't perfect. Always check the experience line in the full listing before applying.
- If nothing new matches on a day, it sends nothing.
