#!/usr/bin/env python3
import os
"""Create cron jobs on cron-job.org for TikTok automation.
Posts at: 9:00 AM and 6:00 PM Beirut time (different from Instagram to spread content).
"""
import requests
import json

API_KEY = os.environ.get("CRONJOB_API_KEY", "")
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

GH_TOKEN = os.environ.get("GH_TOKEN", "")
WORKFLOW_URL = "https://api.github.com/repos/gotrendy-lb/gotrendy-tiktok-automation/actions/workflows/post_tiktok.yml/dispatches"

def make_job(title, hour, minute):
    return {
        "job": {
            "title": title,
            "enabled": True,
            "saveResponses": False,
            "url": WORKFLOW_URL,
            "requestMethod": 1,  # POST
            "requestTimeout": 30,
            "redirectSuccess": False,
            "folderId": 0,
            "extendedData": {
                "headers": {
                    "Authorization": f"token {GH_TOKEN}",
                    "Content-Type": "application/json"
                },
                "body": "{\"ref\":\"main\"}"
            },
            "schedule": {
                "timezone": "Asia/Beirut",
                "hours": [hour],
                "mdays": [-1],
                "minutes": [minute],
                "months": [-1],
                "wdays": [-1],
                "expiresAt": 0
            }
        }
    }

tiktok_jobs = [
    ("GoTrendy TikTok 9AM Beirut", 9, 0),
    ("GoTrendy TikTok 6PM Beirut", 18, 0),
]

print("Creating TikTok cron jobs...")
for title, hour, minute in tiktok_jobs:
    payload = make_job(title, hour, minute)
    resp = requests.put(
        "https://api.cron-job.org/jobs",
        headers=HEADERS,
        json=payload
    )
    if resp.status_code == 200:
        job_id = resp.json().get("jobId")
        print(f"✅ Created: {title} (ID: {job_id})")
    else:
        print(f"❌ Failed: {title} — {resp.status_code}: {resp.text}")

print("\nDone! TikTok posts will run at 9:00 AM and 6:00 PM Beirut time daily.")
