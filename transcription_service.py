from config import MODEL_PATH, WHISPER_BINARY
from utils import run_subprocess


class TranscriptionService:
    def __init__(self, wav_file, csv_file):
        self.wav_file = wav_file
        self.csv_file = csv_file

    def transcribe_audio(self):
        args = [
            WHISPER_BINARY,
            "-m",
            MODEL_PATH,
            "-ocsv",
            "-f",
            f"{self.wav_file}",
            "-t",
            "8",
            "-of",
            f"media/{self.csv_file}",
        ]  # ,[WHISPER_BINARY, "-m", MODEL_PATH, "-ocsv", "-f", self.wav_file, "-of", self.csv_file]
        yield from run_subprocess(args)
