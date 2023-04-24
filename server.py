import asyncio
import os
import re
import subprocess
import uuid
from asyncio.subprocess import PIPE
from datetime import timedelta

from flask import (Flask, Response, redirect, render_template, request,
                   send_file, stream_with_context)
from flask_cors import CORS

from speaker_diff import StandardizeOutput
from whisperlog import setup_logger

app = Flask("PODV2T")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
CORS(app, send_wildcard=True, resources={r"/": {"origins": ""}})

BASE_PATH = os.getcwd()
MODELS_PATH = os.path.join(BASE_PATH, 'models')
MODEL_PATH = os.path.join(MODELS_PATH, 'ggml-model-whisper-base.en.bin')
WHISPER_BINARY = os.path.join(BASE_PATH, 'bin', 'main')
MEDIA_PATH = os.path.join(BASE_PATH, 'media')

log_file = os.path.join(os.getcwd(), 'app.log')

logger = setup_logger('app', log_file)

if not os.path.exists(MEDIA_PATH):
    os.makedirs(MEDIA_PATH)


def run_subprocess(args, tempfile):
    try:
        logger.info("Running subprocess %s", args)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            if line.startswith(b"["):
                line = line.decode("utf8").strip().split("]")[1]
                logger.info("line: %s", line)
                tempfile.write(line)
                yield f"{line}"
            else:
                continue
    except Exception as e:
        logger.error("An error occurred while running subprocess %s: %s", args, e)
    finally:
        if proc:
            logger.info("Terminating subprocess")
            proc.terminate()


def transcribe_audio(wav_file, csv_file):
    args = [WHISPER_BINARY, "-m", MODEL_PATH, "-ocsv", "-f", wav_file, "-of", csv_file]
    try:
        with open(os.path.join(MEDIA_PATH, f'transcript_{uuid.uuid4()}.txt'), "a", encoding="utf-8") as tmp_file:
            logger.info(f"Transcribing {wav_file} to {csv_file}")
            logger.debug(f"Running command: {' '.join(args)}")
            logger.debug("Command output:")
            yield from run_subprocess(args, tmp_file)
    except Exception as e:
        logger.error("An error occurred while transcribing audio for file %s: %s", wav_file, e)
        raise  # This will raise the exception to the calling function
    else:
        logger.info("Transcription complete")


def transcript_generator(uuid_str):
    temp_dir = "media"
    base_file_name = f"{temp_dir}/{uuid_str}"
    wav_file_path = f"{base_file_name}.wav"
    csv_file_path = f"{MEDIA_PATH}/{uuid_str}.csv"

    try:
        yield "Transcribing audio...\n"
        with open(os.path.join(temp_dir, f'transcript_{uuid.uuid4()}.txt'), "a", encoding="utf-8") as tmp_file:
            yield from transcribe_audio(wav_file_path, csv_file_path)
        speaker_diar = StandardizeOutput(wav_file_path=wav_file_path, csv_file_path=csv_file_path)
        speaker_diar.get_standardized_output()
        yield f"Speaker diff output:\n{speaker_diar.final_output}\n"
    except Exception as e:
        logger.error("An error occurred while transcribing audio for file %s: %s", uuid_str, e)
        raise  # This will raise the exception to the calling function
    else:
        yield f"\nTranscribed: http://localhost:8833/download/{uuid_str}.csv"
    finally:
        if os.path.exists(wav_file_path):
            os.remove(wav_file_path)
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
        with open(os.path.join(temp_dir, f'transcript_{uuid.uuid4()}.txt'), "a", encoding="utf-8") as tmp_file:
            tmp_file.write("\n")


@app.route('/transcribe', methods=["GET", "POST"])
def transcription():
    gen_uuid_str = request.query_string.split(b'=')[1].decode('utf-8').split('.')[0]
    logger.info(f"gen_uuid_str: {gen_uuid_str}")
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

            p1 = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name:stream_tags=language",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                f'media/{file_new}',
                stdout=PIPE,
            )
            codec = await p1.stdout.read()
            codec = codec.decode("utf8").strip()
            logger.info("codec is %s", codec)
            if codec != 'pcm_mulaw':
                logger.info('CONVERTING FILE TO WAV....')
                process_convert = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-loglevel",
                    "panic",
                    "-i",
                    f"media/{file_new}",
                    "-y",
                    "-probesize",
                    "32",
                    "-ar",
                    "16000",
                    "-ac",
                    "1",
                    "-acodec",
                    "pcm_s16le",
                    f"media/{file_converted}",
                )
                await process_convert.communicate()
                logger.info('CONVERTED FILE TO WAV!')
                os.remove(f"media/{file_new}")

            return redirect(f"/transcribe?file={file_converted}")
        except Exception as e:
            logger.error("file not found ... %s", e)
            return redirect('/')


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

'''

def download_and_resample_audio(source_url, base_file_name):
    """
    Download the audio file from the specified source URL, resample it to 16kHz
    and convert it to a WAV file.

    Args:
        source_url (str): The URL of the source audio file.
        base_file_name (str): The base filename for the downloaded and converted files.

    Returns:
        None
    """
    subprocess.run(
        ['yt-dlp', '-f', 'bestaudio[ext=m4a]/best[ext=mp4]/best', '--xattrs', source_url, '-o', f'{base_file_name}.mp4']
    )
    subprocess.run(
        [
            'ffmpeg',
            '-i',
            f'{base_file_name}.mp4',
            '-hide_banner',
            '-loglevel',
            'error',
            '-ar',
            '16000',
            '-ac',
            '1',
            '-c:a',
            'pcm_s16le',
            '-y',
            f'{base_file_name}.wav',
        ]
    )
    logger.info("Resampled audio")


def generate(proc, tmp_file):
    for line in iter(proc.stdout.read, ''):
        if not line:
            break
        if line.startswith(b"output_csv:"):
            break
        if not line.startswith(b"whisper_") and not line.startswith(b"main:"):
            line = line.decode("utf8").strip()
            tmp_file.write(line)
            tmp_file.write("\n")
            yield f"{line}"
        else:
            continue


def generate_with_ts(proc, tmp_file):
    for line in iter(proc.stdout.readline, ''):
        if line.startswith(b"["):
            line = line.decode("utf8").strip()
            tmp_file.write(line)
            tmp_file.write("\n")
            yield f"{line}"
        if not line:
            break
        else:
            continue

# def transcribe_audio(base_file_name, uuid_str):
#     proc = subprocess.Popen(
#         [WHISPER_BINARY, '-m', MODEL_PATH, '-ocsv', '-f', f'{base_file_name}.wav', '-of', f'{MEDIA_PATH}/{uuid_str}'],
#         stdout=subprocess.PIPE,
#     )
#     transcript_file = open(f"{MEDIA_PATH}/transcript_{uuid_str}.txt", "a", encoding="utf-8")
#     # Generator for the transcript
#     for line in iter(proc.stdout.readline, b''):
#         if not line:
#             break
#         if line.startswith(b"["):
#             line = line.decode("utf8").strip().split("]")[1]
#             transcript_file.write(line)
#             yield f"{line}\n"
#         else:
#             continue

#     # Run speaker_diff
#     wav_file_path = f"{base_file_name}.wav"
#     csv_file_path = f"{MEDIA_PATH}/{uuid_str}.csv"
#     speaker_diar = StandardizeOutput(wav_file_path=wav_file_path, csv_file_path=csv_file_path)
#     speaker_diar.get_standardized_output()
#     yield f"Speaker diff output:\n{speaker_diar.final_output}\n"

'''
