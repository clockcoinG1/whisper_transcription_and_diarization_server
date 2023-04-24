import os
import uuid
from config import MEDIA_PATH, WHISPER_BINARY, MODEL_PATH
from utils import run_subprocess

class TranscriptionService:
    def __init__(self, wav_file, csv_file):
        self.wav_file = wav_file
        self.csv_file = csv_file

    def transcribe_audio(self):
        args = [WHISPER_BINARY, "-m", MODEL_PATH, "-ocsv", "-f", self.wav_file, "-of", self.csv_file]
        yield from run_subprocess(args)