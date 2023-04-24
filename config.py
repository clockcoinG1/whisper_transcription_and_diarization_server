from datetime import timedelta

SESSION_TYPE = 'filesystem'
PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
BASE_PATH = os.getcwd()
MODELS_PATH = os.path.join(BASE_PATH, 'models')
MODEL_PATH = os.path.join(MODELS_PATH, 'ggml-model-whisper-base.en.bin')
WHISPER_BINARY = os.path.join(BASE_PATH, 'bin', 'main')
MEDIA_PATH = os.path.join(BASE_PATH, 'media')
LOG_FILE = os.path.join(os.getcwd(), 'app.log')