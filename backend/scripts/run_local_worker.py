import subprocess
import sys


def run():
    print("Starting Celery worker for marketing OS...")
    cmd = [
        "celery",
        "-A",
        "app.tasks.celery_app",
        "worker",
        "--loglevel=info",
        "-Q",
        "orchestrator_queue,publishing_queue,media_queue,analytics_queue",
    ]
    if "--beat" in sys.argv or "-B" in sys.argv:
        cmd.append("-B")
    subprocess.run(cmd)


if __name__ == "__main__":
    run()
