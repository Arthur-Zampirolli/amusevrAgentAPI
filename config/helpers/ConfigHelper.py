import os

class ConfigHelper:

    def __init__(self):
        self.ollama_api_url = os.environ.get("OLLAMA_API_URL")
        self.ollama_port = os.environ.get("OLLAMA_PORT")
        self.voice = os.environ.get("VOICE")
        self.server_address = os.environ.get("SERVER_ADDRESS")
        self.server_port = os.environ.get("SERVER_PORT")
        self.offload_level = int(os.environ.get("OFFLOAD_LEVEL"))
        self.whisper_model = os.environ.get("WHISPER_MODEL")
        self.whisper_precision = os.environ.get("WHISPER_PRECISION")
    def show_config(self):

        print(self.ollama_api_url)
        print(self.ollama_port)
        print(self.voice)
        print(self.server_address)
        print(self.server_port)
        print(self.offload_level)
        print(self.whisper_model)
        print(self.whisper_precision)

