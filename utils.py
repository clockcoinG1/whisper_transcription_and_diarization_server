import os
import subprocess

from config import LOG_FILE, MEDIA_PATH
from whisperlog import setup_logger

logger = setup_logger('PODV2T', LOG_FILE)


def run_subprocess(args):
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        for line in iter(proc.stdout.readline, b''):
            logger.info(f"Line: {line}")
            if not line:
                logger.info("End of transcript")
                yield "\nEnd of transcript\n"
                break
            if line.startswith(b"["):
                line = line.decode("utf8").strip().split("]")[1].strip()
                logger.info(f"{line}")
                yield f"{line}"
            else:
                logger.info(f"Skipping line: {line}")
                continue
    except OSError as e:
        # Handle this error, e.g. by logging the failure.
        # If the error is recoverable, you can retry the command
        # a few times before giving up.
        logger.error(f"OS Error: {e}")
        yield f"Error: {e}"
        return

    except Exception as e:
        logger.error(f"Error: {e}")
        yield f"Error: {e}"
    finally:
        proc.terminate()
        logger.info(f"Process terminated: {args}, {proc.returncode}")


def create_media_directory():
    if not os.path.exists(MEDIA_PATH):
        os.makedirs(MEDIA_PATH)


create_media_directory()
