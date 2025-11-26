# Gmail Job Tracker

A small personal tool that turns your **Gmail inbox + OpenAI** into a searchable job application tracker.

It:

- Scans your Gmail for **application confirmations** and **rejection emails**
- Builds/updates a local `jobs.csv` with company, role title, status, dates, and snippets
- Uses the **OpenAI API** to generate a **one-line summary**, **key skills**, and **salary info (if present)** for each job
- Outputs a cleaned version as `jobs_with_summaries.csv` that you can open in Excel or any spreadsheet tool

This is meant to replace “trying to remember where I applied” with a single, up-to-date CSV.

---

## Features

- 🔍 **Gmail sync**
  - Looks for “application received”, “thank you for applying”, etc. → marks as `Applied`
  - Looks for “we regret to inform you”, “decided not to move forward”, etc. → marks as `Rejected`
  - Writes everything into `jobs.csv` (or updates existing rows)

- 🧠 **OpenAI-powered summarizer**
  - For each job, creates:
    - `summary`: one-sentence description of the role
    - `skills`: 3–8 key skills/keywords
    - `salary`: extracted salary string or `"unknown"`
  - Reads from:
    - `job_description` (your pasted JD text, optional but recommended)
    - `job_text` (email snippets from Gmail)

- 🧾 **Local & private by design**
  - All data lives in local CSV files
  - API keys, Gmail credentials, and personal data are **not** committed to Git

- **Useful Commands**
  - py gmail_sync.py scan-confirmations
  - py gmail_sync.py scan-rejections
  - py gmail_sync.py scan-all
  - py job_tracker.py --input jobs.csv --output jobs_with_summaries.csv

---
## Setup

- **OpenAI API key**
  - Create an API key on the OpenAI platform.
  - Copy .env.example to .env and set:
    - OPENAI_API_KEY=sk-...your-key-here...
  - Make sure .env is in .gitignore.

- **Gmail API credentials**
    - Create a project in Google Cloud Console.
    - Enable the Gmail API.
    - Configure OAuth consent screen:
    - Add your Gmail as a Test user 
    - Create an OAuth Client of type Desktop App
    - Download the JSON and save it as:
        - gmail-job-tracker/credentials.json


## Project structure

```text
gmail-job-tracker/
  ├─ job_tracker.py          # OpenAI summarizer (jobs.csv -> jobs_with_summaries.csv)
  ├─ gmail_sync.py           # Gmail API sync (fills/updates jobs.csv)
  ├─ requirements.txt        # Python dependencies
  ├─ .env.example            # Example env file for OpenAI key
  ├─ jobs_example.csv        # Optional fake sample data for the repo
  ├─ .gitignore
  └─ README.md
