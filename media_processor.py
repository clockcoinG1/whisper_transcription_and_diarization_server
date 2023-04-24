import os
import shutil
import subprocess
import uuid
from abc import ABC, abstractmethod

from config import *
from speaker_diff import StandardizeOutput


class MediaSource(ABC):
    @abstractmethod
    def get_media(self):
        pass


class URLMediaSource(MediaSource):
    def __init__(self, url):
        self.url = url

    def get_media(self):
        return self.url


class FileMediaSource(MediaSource):
    def __init__(self, file_path):
        self.file_path = file_path

    def get_media(self):
        return self.file_path


class MediaProcessor:
    def __init__(self, media_source):
        self.media_source = media_source
        self.temp_dir = os.path.join(os.getcwd(), "media")
        self.uuid_str = str(uuid.uuid4())
        self.base_file_name = f"{self.temp_dir}/{self.uuid_str}"

    def download_media(self):
        media = self.media_source.get_media()
        if isinstance(self.media_source, URLMediaSource):
            subprocess.run(
                [
                    "yt-dlp",
                    "-f",
                    "bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "--xattrs",
                    f"{media}",
                    "-o",
                    f"{self.base_file_name}",
                ]
            )
        elif isinstance(self.media_source, FileMediaSource):
            # Copy the file to the temp directory
            shutil.copy2(media, f"{self.base_file_name}")
        else:
            raise ValueError("Unsupported media source")

    def extract_audio_and_resample(self):
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                f"{self.base_file_name}",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-y",
                f"{self.base_file_name}.wav",
            ]
        )

    def transcribe_audio(self):
        proc = subprocess.Popen(
            [
                WHISPER_BINARY,
                "-m",
                MODEL_PATH,
                "-ocsv",
                "-f",
                f"{self.base_file_name}.wav",
                "-t",
                "8",
                "-of",
                f"media/{self.uuid_str}.csv",
            ],
            stdout=subprocess.PIPE,
        )
        transcript_file = open(f"{self.temp_dir}/transcript_{self.uuid_str}.txt", "a", encoding="utf-8")

        for line in iter(proc.stdout.readline, ""):
            if not line:
                yield f"<a href='http://localhost:8833/{self.uuid_str}.csv' target='_blank'>Download CSV</a>"
                break
            if line.startswith(b"["):
                line = line.decode("utf8").strip().split("]")[1]
                transcript_file.write(line)
                yield f"{line}"
            else:
                continue

    def run_speaker_diff(self):
        wav_file_path = f"{self.base_file_name}.wav"
        csv_file_path = f"{self.base_file_name}.csv"
        speaker_diar = StandardizeOutput(wav_file_path=wav_file_path, csv_file_path=csv_file_path)
        speaker_diar.get_standardized_output()
