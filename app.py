import os
import re
import uuid

from flask import Flask, Response, render_template, request, send_file, stream_with_context
from flask_cors import CORS

from config import *
from media_processor import FileMediaSource, MediaProcessor, URLMediaSource
from speaker_diff import StandardizeOutput
from transcription_service import TranscriptionService
from utils import logger

app = Flask("PODV2T")
app.config['SESSION_TYPE'] = SESSION_TYPE
app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
CORS(app, send_wildcard=True, resources={r"/": {"origins": ""}})


def transcript_generator(uuid_str):
    temp_dir = "media"
    base_file_name = f"{temp_dir}/{uuid_str}"
    wav_file_path = f"{base_file_name}.wav"
    csv_file_path = f"{base_file_name}.csv"

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


@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == 'GET':
        return render_template('index.html')


@app.route('/t', methods=['GET', 'POST'])
def upload_file():
    file = request.files['file']
    uuid_str = str(uuid.uuid4())
    file_new = f"{uuid_str}"
    file.save(os.path.join('media', file_new))

    def generate(file_new=file_new):
        file_media_source = FileMediaSource(os.path.join('media', file_new))
        media_processor = MediaProcessor(file_media_source)
        yield f"Preparing audio file ..."
        media_processor.download_media()
        media_processor.extract_audio_and_resample()
        for line in media_processor.transcribe_audio():
            yield line

    return Response(stream_with_context(generate(file_new)))


@app.route('/url', methods=["GET", "POST"])
def tr_url():
    def gen():
        source_url = request.form.get('url')
        url_media_source = URLMediaSource(source_url)
        media_processor = MediaProcessor(url_media_source)

        yield f"Downloading media.... {source_url}"
        media_processor.download_media()

        yield "Extracting Audio and Resampling..."
        media_processor.extract_audio_and_resample()

        for line in media_processor.transcribe_audio():
            yield line

        # media_processor.run_speaker_diff()

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
