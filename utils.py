import os
import subprocess
import uuid
from whisperlog import setup_logger
from config import LOG_FILE, MEDIA_PATH

logger = setup_logger('app', LOG_FILE)

def run_subprocess(args):
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            yield line.decode("utf8").strip()
    except Exception as e:
        logger.error("An error occurred while running subprocess %s: %s", args, e)
    finally:
        if proc:
            proc.terminate()

def create_media_directory():
    if not os.path.exists(MEDIA_PATH):
        os.makedirs(MEDIA_PATH)

create_media_directory()