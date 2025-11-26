import os
import argparse
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI


def load_api_client() -> OpenAI:
    """
    Load OpenAI client using OPENAI_API_KEY from .env
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not found. Set it in your .env file.")
    return OpenAI(api_key=api_key)


def build_prompt(row: pd.Series) -> str:
    """
    Build a prompt for a single job row.
    Expects columns: company, role_title, job_text.
    """
    company = row.get("company", "")
    role_title = row.get("role_title", "")
    job_text = row.get("job_text", "")

    return f"""
You are helping a student track their job applications.

Job title: {role_title}
Company: {company}

Here is some text related to the job (from the description, notes, or email):
---
{job_text}
---

Your tasks:

1) Write a single-sentence summary of what this job is about. Maximum 25 words.
2) List 3–8 key skills or keywords the role seems to care about.
3) If a salary or salary range is mentioned, extract it as a short string
   (for example: "$30–35/hr" or "$95k–115k + bonus").
   If not mentioned, use "unknown".

Return your answer as JSON with this exact structure:

{{
  "summary": "one-line summary here",
  "skills": ["Skill1", "Skill2", "Skill3"],
  "salary": "salary or 'unknown'"
}}
"""


def summarize_job(client: OpenAI, row: pd.Series) -> dict:
    """
    Call the OpenAI API to summarize one job row.
    Returns a dict with keys: summary, skills, salary.
    """
    prompt = build_prompt(row)

    response = client.responses.create(
        model="gpt-5.1-mini",
        input=prompt,
        response_format={"type": "json_object"},
    )

    # Extract parsed JSON from the first output
    parsed = response.output[0].content[0].parsed
    return parsed


def process_jobs(input_path: Path, output_path: Path) -> None:
    """
    Read jobs from CSV, summarize missing ones, and write updated CSV.
    """
    client = load_api_client()

    df = pd.read_csv(input_path)

    # Ensure these columns exist
    if "summary" not in df.columns:
        df["summary"] = ""
    if "skills" not in df.columns:
        df["skills"] = ""
    if "salary" not in df.columns:
        df["salary"] = ""

    updated = 0

    for idx, row in df.iterrows():
        # Skip rows that already have a summary
        if isinstance(row.get("summary", ""), str) and row["summary"].strip():
            continue

        print(f"Summarizing: {row.get('company', '')} - {row.get('role_title', '')} ...")
        try:
            result = summarize_job(client, row)

            df.at[idx, "summary"] = result.get("summary", "")

            skills_list = result.get("skills", [])
            if isinstance(skills_list, list):
                df.at[idx, "skills"] = ", ".join(skills_list)
            else:
                df.at[idx, "skills"] = str(skills_list)

            df.at[idx, "salary"] = result.get("salary", "")

            updated += 1
        except Exception as e:
            print(f"  Error summarizing row {idx}: {e}")

    df.to_csv(output_path, index=False)
    print(f"\nDone. Updated {updated} job(s).")
    print(f"Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Summarize job applications using OpenAI and update a CSV."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="jobs.csv",
        help="Path to input CSV (default: jobs.csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="jobs_with_summaries.csv",
        help="Path to output CSV (default: jobs_with_summaries.csv)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    process_jobs(input_path, output_path)


if __name__ == "__main__":
    main()
