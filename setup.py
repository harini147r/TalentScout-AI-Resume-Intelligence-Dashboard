import os
import subprocess

os.makedirs("resume-screener-app", exist_ok=True)
os.chdir("resume-screener-app")

subprocess.run(["python", "-m", "venv", "env"])