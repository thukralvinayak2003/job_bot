from .linkedin_apply import LinkedInApply
from .utils.job_filtering import get_new_jobs_only
from .indeed_apply import IndeedApply
from .naukri_apply import NaukriApply

# Export main classes and functions
__all__ = ['LinkedInApply', 'IndeedApply', 'NaukriApply', 'get_new_jobs_only']
