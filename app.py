import os
import sys
import uuid

from flask import Flask, Response, render_template, request, send_file, stream_with_context
from flask_cors import CORS

from config import *
from media_processor import FileMediaSource, MediaSource, MediaTranscriptionFacade, URLMediaSource
from utils import logger

app = Flask("PODV2T")
app.config['SESSION_TYPE'] = SESSION_TYPE
app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
CORS(app, send_wildcard=True, resources={r"/": {"origins": ""}})


def gen(url_media_source: MediaSource):
    transcription_facade = MediaTranscriptionFacade(url_media_source)

    try:
        for line in transcription_facade.transcribe_media():
            yield line
    except Exception as e:
        logger.error(f"An error occurred while extracting audio {e}")
        yield f"An error occurred while extracting audio {e}"
    finally:
        yield "<br> Transcription completed!"


@app.route('/', methods=["GET"])
def index():
    if request.method == 'GET':
        return render_template('index.html')


@app.route('/t', methods=['GET', 'POST'])
def upload_file():
    file = request.files['file']
    file_new = f"{str(uuid.uuid4())}"
    file.save(os.path.join('media', file_new))

    return Response(stream_with_context(gen(FileMediaSource(os.path.join('media', file_new)))))


@app.route('/url', methods=["GET", "POST"])
def tr_url():
    source_url = request.form.get('url')
    url_media_source = URLMediaSource(source_url)

    return Response(stream_with_context(gen(url_media_source)))


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


def main():
    logger.info('Starting server...')
    try:
        port = int(os.environ.get('PORT') if os.environ.get('PORT') is not None else 8833)
        app.run(debug=False, port=port)
    except Exception as e:
        logger.error('Failed to start server: %s', e)
        sys.exit(1)
    finally:
        logger.info('Server has stopped.')


if __name__ == "__main__":
    main()
