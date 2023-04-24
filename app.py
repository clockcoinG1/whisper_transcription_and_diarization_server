import os
import uuid

from flask import Flask, Response, render_template, request, send_file, stream_with_context
from flask_cors import CORS

from config import *
from media_processor import FileMediaSource, MediaProcessor, URLMediaSource, MediaTranscriptionFacade
from speaker_diff import StandardizeOutput
from utils import logger

app = Flask("PODV2T")
app.config['SESSION_TYPE'] = SESSION_TYPE
app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
CORS(app, send_wildcard=True, resources={r"/": {"origins": ""}})


@app.route('/', methods=["GET"])
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
        transcription_facade = MediaTranscriptionFacade(file_media_source)

        try:
            for line in transcription_facade.transcribe_media():
                yield line
        except Exception as e:
            logger.error("An error occurred while extracting audio for file %s: %s", uuid_str, e)
            yield f"An error occurred while extracting audio for file {uuid_str}: {e}"
            return
        finally:
            yield f"<br> Transcription completed!"

    return Response(stream_with_context(generate(file_new)))


@app.route('/url', methods=["GET", "POST"])
def tr_url():
    def gen():
        source_url = request.form.get('url')
        url_media_source = URLMediaSource(source_url)
        transcription_facade = MediaTranscriptionFacade(url_media_source)

        try:
            for line in transcription_facade.transcribe_media():
                yield line
        except Exception as e:
            logger.error("An error occurred while extracting audio for URL %s: %s", source_url, e)
            yield f"An error occurred while extracting audio for URL {source_url}: {e}"
            return
        finally:
            yield f"<br> Transcription completed!"

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
