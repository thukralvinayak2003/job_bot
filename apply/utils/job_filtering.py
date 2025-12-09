from typing import List, Dict
from database import db

def get_new_jobs_only(jobs: List[Dict]) -> List[Dict]:
    """Filter out jobs that are already in the database"""
    applied_links = db.get_applied_job_links()
    new_jobs = []
    skipped_count = 0
    
    for job in jobs:
        if job.get("link") not in applied_links:
            new_jobs.append(job)
        else:
            skipped_count += 1
            print(f"⏭️  Skipping already applied job: {job.get('role')} @ {job.get('company')}")
    
    print(f"Filtered {skipped_count} already applied jobs, {len(new_jobs)} new jobs remaining")
    return new_jobs

def is_job_already_applied(job_link: str) -> bool:
    """Check if job is already applied"""
    return db.is_job_applied(job_link)