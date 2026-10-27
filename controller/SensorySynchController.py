import base64
import mimetypes

import requests
from fastapi import HTTPException

from config.helpers.ConfigHelper import ConfigHelper

VALID_MODULES = [
    "effectLocalization",
    "fireLocalization",
    "sunLocalization",
    "sceneUnderstanding",
]


class SensorySynchController:

    def __init__(self, config: ConfigHelper):
        self.config = config
        env_tuple = (self.config.sensorysynch_api_url, self.config.sensorysynch_api_port)
        self.base_url = "http://" + ":".join(env_tuple)

    def build_payload(self, video_path: str = None, video_bytes: bytes = None,
                      modules: list[str] = None, user_id: str = None,
                      mime_type: str = None) -> dict:
        selected_modules = modules if modules else VALID_MODULES
        invalid_modules = [module for module in selected_modules if module not in VALID_MODULES]
        if invalid_modules:
            raise HTTPException(status_code=400, detail=f"Módulos inválidos: {', '.join(invalid_modules)}")

        if video_path:
            mime = mime_type or mimetypes.guess_type(video_path)[0] or "video/mp4"
            try:
                with open(video_path, "rb") as handle:
                    video_bytes = handle.read()
            except OSError as e:
                raise HTTPException(status_code=400, detail=f"Erro ao ler o vídeo: {e}")
        elif video_bytes:
            mime = mime_type or "video/mp4"
        else:
            raise HTTPException(status_code=400, detail="Informe video_path ou video_bytes")

        payload = {
            "video": "data:%s;base64,%s" % (mime, base64.b64encode(video_bytes).decode("ascii")),
            "modules": selected_modules,
        }
        if user_id:
            payload["user_id"] = user_id
        return payload

    async def upload_video(self, video_path: str = None, video_bytes: bytes = None,
                           modules: list[str] = None, user_id: str = None,
                           mime_type: str = None) -> dict:
        payload = self.build_payload(video_path, video_bytes, modules, user_id, mime_type)
        try:
            response = requests.post(
                self.base_url + "/api/upload_video",
                json=payload,
                headers={"Accept": "application/json"},
                timeout=600,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Erro de comunicação com o SensorySynch360: {e}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def get_modules_status(self, job_uid: str) -> dict:
        try:
            response = requests.get(
                self.base_url + "/api/get_modules_status",
                params={"user_id": job_uid},
                headers={"Accept": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=503, detail=f"Erro de comunicação com o SensorySynch360: {e}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
