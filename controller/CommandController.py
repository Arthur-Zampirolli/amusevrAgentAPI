from time import sleep

from fastapi import HTTPException

from config.helpers.ConfigHelper import ConfigHelper
from controller.AudioSynthController import AudioSynthController
from controller.XMLController import XMLController
from faster_whisper import WhisperModel
import torch
import shutil
import os
import requests
import json

class CommandController:
    def __init__(self, config:ConfigHelper):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        #self.device = "cpu"
        #precision = "float16" if self.device == "cuda" else "int8"
        #precision = "int8"
        self.config = config
        self.model = WhisperModel(self.config.whisper_model, device=self.device, compute_type=self.config.whisper_precision)
    async def transcribe_audio(self, file):
        try:
            if self.config.offload_level < 1:

                temp_filename = f"debug_{file.filename}"
                with open(temp_filename, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                segments, info = self.model.transcribe(temp_filename, beam_size=5)

                full_text = "".join([segment.text for segment in segments])

                print(f"Transcrição concluída: {full_text}")

                return {
                    "text": full_text.strip(),
                    "language": info.language,
                    "probability": info.language_probability
                }
            else:
                resp = requests.post()
        except Exception as e:
            print(e)
            raise HTTPException(status_code=500, detail=f"Erro interno no processamento: {e}")
    def clean_dados_ia(self, dados_ia: str):
        # 1. Limpa qualquer formatação de bloco de código Markdown que a IA tenha gerado
        dados_ia_limpo = dados_ia.strip()
        if dados_ia_limpo.startswith("```"):
            # Remove a linha inicial (ex: ```json ou ```)
            dados_ia_limpo = "\n".join(dados_ia_limpo.split("\n")[1:])
        if dados_ia_limpo.endswith("```"):
            # Remove os três últimos crases
            dados_ia_limpo = dados_ia_limpo.rsplit("```", 1)[0]

        dados_ia_limpo = dados_ia_limpo.strip()
        return dados_ia_limpo

    async def process_command(self, command: str, xml_controller:XMLController, scene_id):
        #chama o ollama com alguns parâmetros
        env_tuple= (self.config.ollama_api_url,self.config.ollama_port)
        ollama_url = "http://"+":".join(env_tuple)
        xml_string = xml_controller.get_xml_data()
        audio_controller = AudioSynthController()
        request_dict = {
            "model": "qwen2.5-coder:14b",
            "messages": [
                {
                    "role": "system",
                    "content": f"{open('./config/system.txt', 'r', encoding='utf-8').read().strip()}"
                },
                {
                    "role": "user",
                    "content": f"Usuário disse: '{command}'\n\n XML Atual:{xml_string}"
                }
            ],
            "options": {
                "temperature": 0.1,
                "num_ctx": 16384,  # Mantido alto para o XML respirar
                "num_predict": 1024
            },
            "stream": False
            # "format": "json" <-- Pode deixar comentado por enquanto para testar o texto puro
        }
        print(request_dict)
        #waiting to gpu memory get free
        sleep(1)
        try:
            # 1. Chama o agente local no Ollama
            resposta_ollama = requests.post(ollama_url+'/api/chat', json=request_dict)
            resposta_ollama.raise_for_status()
            print(resposta_ollama.json())
            # 2. Faz o parse da resposta de texto para o dicionário JSON correspondente
            dados_ia = resposta_ollama.json().get("message")

            dados_finais = json.loads(self.clean_dados_ia(dados_ia['content']))

            # 3. Executa o pós-processamento de injeção no XML
            tags = ''
            for tag in dados_finais['novas_tags']:
                tags = tags + f" {tag}"
            xml_controller.add_property(tags.strip(), scene_id)
            dados_finais['xml_final'] = xml_controller.get_xml_data()
            dados_finais['id_cena_alvo'] = scene_id
            # 4. Retorna a estrutura para o frontend (que usará a 'fala_usuario' no TTS)
            audio = await audio_controller.synth_audio(dados_finais['fala_usuario'], os.environ.get('VOICE'))
            #dados_finais['file'] = audio
            return dados_finais, audio

        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Erro de comunicação com o Ollama: {e}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro interno no processamento: {e}")
