import subprocess
import sys

def run():
    print("Starting Celery worker for marketing OS...")
    subprocess.run([
        "celery", "-A", "app.tasks.celery_app", "worker",
        "--loglevel=info", "-Q", "orchestrator_queue,publishing_queue,media_queue,analytics_queue"
    ])

if __name__ == "__main__":
    run()
