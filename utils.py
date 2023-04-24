import os
import subprocess

from config import LOG_FILE, MEDIA_PATH
from whisperlog import setup_logger
from whisperlog import setup_logger

logger = setup_logger('PODV2T', LOG_FILE)


def run_subprocess(args):
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    try:
        for line in iter(proc.stdout.readline, b''):
            if not line:
                yield f"\nEnd of transcript\n"
                break
            if line.startswith(b"["):
                line = line.decode("utf8").strip().split("]")[1]
                yield f"{line}"
            else:
                continue
    except Exception as e:
        logger.error("An error occurred while running subprocess %s: %s", args, e)
    finally:
        if proc:
            proc.terminate()


def create_media_directory():
    if not os.path.exists(MEDIA_PATH):
        os.makedirs(MEDIA_PATH)


create_media_directory()
