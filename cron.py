import time
import queue
import logging
import uuid
from datetime import datetime
import croniter

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cron_scheduler")

# Need to set up environment context for Flask/utils
from dotenv import load_dotenv
load_dotenv()

from backend.utils import get_drive_service
from backend.db import get_db_connection, save_user_config, get_token
from backend.jobs import run_compression_job, jobs

def run_due_jobs():
    logger.info("Checking for due jobs...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now = time.time()
        
        # Find jobs that have a cron schedule, and their next_run is either due or 0 (meaning never run yet)
        # But wait, if next_run is 0, it shouldn't run unless the schedule dictates it.
        # Actually, if next_run > 0 and next_run <= now, it's due.
        cursor.execute("SELECT * FROM configs WHERE cron_schedule != '' AND next_run > 0 AND next_run <= ?", (now,))
        due_configs = cursor.fetchall()
        
        if not due_configs:
            logger.info("No jobs are currently due.")
            return

        for row in due_configs:
            config = dict(row)
            config['delete_original'] = bool(config['delete_original'])
            email = config['email']
            schedule = config['cron_schedule']
            
            logger.info(f"Running job for user: {email}")
            
            # Check if token exists
            if not get_token(email):
                logger.warning(f"No Google Drive token found for user {email}. Skipping.")
                continue
                
            service = get_drive_service(user_email=email)
            if not service:
                logger.error(f"Failed to get Google Drive service for user {email}. Skipping.")
                continue

            # Prepare job environment
            job_id = f"cron-{str(uuid.uuid4())[:8]}"
            log_q = queue.Queue()
            jobs[job_id] = {
                "id": job_id,
                "user_email": email,
                "status": "running",
                "log_queue": log_q,
                "stats": {"success": 0, "failed": 0, "total": 0},
                "created_at": time.time(),
            }
            
            # Run job synchronously for the cron script (or we can thread it, but synchronous is safer for cron logs)
            logger.info(f"Starting compression for {email} (JobID: {job_id})")
            run_compression_job(job_id, service, config, log_q)
            
            # Drain logs from queue and print them
            while not log_q.empty():
                msg = log_q.get()
                if msg:
                    logger.info(f"[{job_id}] {msg}")
                    
            logger.info(f"Finished job for user {email}. Stats: {jobs[job_id]['stats']}")
            
            # Update next_run
            try:
                import pytz
                tz = pytz.timezone('Asia/Jakarta')
                now_jkt = datetime.now(tz).replace(tzinfo=None)
                itr = croniter.croniter(schedule, now_jkt)
                next_naive = itr.get_next(datetime)
                next_aware = tz.localize(next_naive)
                next_time = next_aware.timestamp()
                config['next_run'] = next_time
                save_user_config(email, config)
                logger.info(f"Updated next run for {email} to {next_aware.isoformat()}")
            except Exception as e:
                logger.error(f"Failed to update next run for {email} with schedule '{schedule}': {e}")
                
    except Exception as e:
        logger.error(f"Error checking jobs: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    logger.info("Starting GD Compress Cron Check")
    run_due_jobs()
    logger.info("Cron Check Done")
