import asyncio
import os
import re
from flask import Flask, Response, redirect, render_template, request, send_file, stream_with_context
from flask_cors import CORS
from speaker_diff import StandardizeOutput
from config import SESSION_TYPE, PERMANENT_SESSION_LIFETIME
from utils import logger
from transcription_service import TranscriptionService

app = Flask("PODV2T")
app.config['SESSION_TYPE'] = SESSION_TYPE
app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
CORS(app, send_wildcard=True, resources={r"/": {"origins": ""}})

def transcript_generator(uuid_str):
    temp_dir = "media"
    base_file_name = f"{temp_dir}/{uuid_str}"
    wav_file_path = f"{base_file_name}.wav"
    csv_file_path = f"{MEDIA_PATH}/{uuid_str}.csv"

    try:
        yield "Transcribing audio...\n"
        transcription_service = TranscriptionService(wav_file_path, csv_file_path)
        yield from transcription_service.transcribe_audio()
        speaker_diar = StandardizeOutput(wav_file_path=wav_file_path, csv_file_path=csv_file_path)
        speaker_diar.get_standardized_output()
        yield f"Speaker diff output:\n{speaker_diar.final_output}\n"
    except Exception as e:
        logger.error("An error occurred while transcribing audio for file %s: %s", uuid_str, e)
        raise
    else:
        yield f"\nTranscribed: http://localhost:8833/download/{uuid_str}.csv"
    finally:
        if os.path.exists(wav_file_path):
            os.remove(wav_file_path)
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)

@app.route('/transcribe', methods=["GET", "POST"])
def transcription():
    if request.method == 'GET':
        return render_template('index.html')
    else:
        gen_uuid_str = request.query_string.split(b'=')[1].decode('utf-8')
        return Response(stream_with_context(transcript_generator(gen_uuid_str)))

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == 'GET':
        return render_template('index.html')

@app.route('/t', methods=['GET', 'POST'])
async def upload_file():
    if request.method == 'POST':
        try:
            file = request.files['file']
            file_name = file.filename
            ext = re.search(r'\.([a-zA-Z0-9]+)$', file_name).group(1)
            uuid_str = str(uuid.uuid4())
            file_new = f"{uuid_str}.{ext}"
            file_converted = f"{uuid_str}.wav"
            file.save(os.path.join('media', file_new))
            logger.info("\033[43mSAVED %s to %s!\033[0m", file_name, file_new)
        except Exception as e:
            logger.error("file not found ... %s", e)

        # Rest of the code remains the same


@app.route('/url', methods=["GET", "POST"])
def tr_url():
    def gen():
        source_url = request.form.get('url')
        temp_dir = os.path.join(os.getcwd(), 'media')
        if not os.path.exists(temp_dir):
            os.mkdir(temp_dir)

        uuid_str = str(uuid.uuid4())
        base_file_name = f"{temp_dir}/{uuid_str}"
        yield f"Downloading media.... {source_url}"
        subprocess.run(
            [
                "yt-dlp",
                "-f",
                "bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--xattrs",
                f"{source_url}",
                "-o",
                f"{base_file_name}.mp4",
            ]
        )
        yield "Extracting Audio and Resampling..."
        logger.info("Extracting audio and resampling...")
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                f"{base_file_name}.mp4",
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
                f"{base_file_name}.wav",
            ]
        )
        logger.info("Transcribing...")
        yield "Transcribing audio..."
        proc = subprocess.Popen(
            [
                WHISPER_BINARY,
                "-m",
                MODEL_PATH,
                "-ocsv",
                "-f",
                f"{base_file_name}.wav",
                "-t",
                "8",
                "-of",
                f"media/{uuid_str}",
            ],
            stdout=subprocess.PIPE,
        )
        transcript_file = open(f"{temp_dir}/transcript_{uuid_str}.txt", "a", encoding="utf-8")

        # Generator for the transcript
        for line in iter(proc.stdout.readline, ''):
            if not line:
                yield f"{uuid_str}.csv"
                break
            if line.startswith(b"["):
                line = line.decode("utf8").strip().split("]")[1]
                transcript_file.write(line)
                yield f"{line}"
            else:
                continue
        # Run speaker_diff
        wav_file_path = f"{base_file_name}.wav"
        csv_file_path = f"{base_file_name}.csv"
        speaker_diar = StandardizeOutput(wav_file_path=wav_file_path, csv_file_path=csv_file_path)
        speaker_diar.get_standardized_output()

    return Response(stream_with_context(gen()))


@app.route('/download/<transcription_type>/<uuid_str>', methods=["GET"])
def download_file(uuid_str, transcription_type):
    temp_dir = os.path.join(os.getcwd(), 'media')
    if transcription_type == "w":
        return send_file(f"{temp_dir}/{uuid_str}.wav", as_attachment=True)
    if transcription_type == "f":
        return send_file(f"{temp_dir}/transcript_{uuid_str}.txt", as_attachment=True)
    if transcription_type == "x":
        return send_file(f"{temp_dir}/{uuid_str}.fo.txt", as_attachment=True)
    if transcription_type == "r":
        return send_file(f"{temp_dir}/{uuid_str}.rttm", as_attachment=True)
    if transcription_type == "c":
        return send_file(f"{temp_dir}/{uuid_str}.csv", as_attachment=True)


@app.route('/static/styles.css', methods=["GET"])
def styles():
    return render_template('styles.css')


if __name__ == '__main__':
    logger.info('Starting server...')
    port = int(os.environ.get('PORT') if os.environ.get('PORT') is not None else 8833)
    app.run(debug=False, port=port)
