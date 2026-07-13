import base64
from pathlib import Path

import fastapi
from fastapi import FastAPI, Form, Query
import uvicorn

from controller.AudioSynthController import AudioSynthController
from controller.CommandController import CommandController
from controller.XMLController import XMLController
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
import torch
import shutil
import os
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

dotenv_path = Path('config/.env')
load_dotenv(dotenv_path=dotenv_path)
app = FastAPI()

#rotear a chamada de envio do xml
@app.post("/send-xml")
async def send_xml(data: dict):
    print(f"Received XML: {data['xml_data']}")
    print(f"Voice: {data['voice']}")
    return {"message": "XML sent successfully"}
@app.post("/update-xml")
async def update_xml(data: dict):
    print(f"Received XML: {data['xml_data']}")
    print(f"Properties: {data['new_data']}")

    controller = XMLController(data['xml_data'])
    controller.add_property(data['new_data'], data['scene_id'])
    data = {
        "xml_data": controller.get_xml_data(),
        "json": controller.get_xml_dict()
    }
    return {
        "message": "XML updated successfully",
        "json": data
    }
#receber comando de voz e realizar a conversão para texto, chamar o agente e atualizar o xml
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    controller = CommandController()
    return await controller.transcribe_audio(file)

@app.post("/process-command")
async def process_command(scene_id: str = Form(...),xml_data: str = Form(...), file: UploadFile = File(...)):
    try:
        print(f"Received XML: {xml_data}")
        #scene_id = data["scene_id"]
        controller = CommandController()
        xml_controller = XMLController(xml_data)
        command = await controller.transcribe_audio(file)
        res, audio_response = await controller.process_command(command['text'], xml_controller,scene_id)
        # Se 'audio_source' for um async generator, consuma os bytes dele
        audio_bytes = b""

        # Verifica se o que voltou é de fato uma StreamingResponse (ou objeto similar com body_iterator)
        if hasattr(audio_response, "body_iterator"):
            # O iterador pode ser assíncrono ou síncrono dependendo de como o TTS foi gerado
            if hasattr(audio_response.body_iterator, "__anext__"):
                async for chunk in audio_response.body_iterator:
                    audio_bytes += chunk
            else:
                for chunk in audio_response.body_iterator:
                    audio_bytes += chunk
        elif isinstance(audio_response, bytes):
            audio_bytes = audio_response
        else:
            # Fallback caso seja um arquivo ou outro tipo de stream bruto
            audio_bytes = audio_response.read()

        # Converte os bytes coletados para string Base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        return {
            'response': res,
            'audio': audio_base64
        }
    except Exception as e:
        return {"error": str(e)}
@app.get("/to-speech")
async def stream_audio(
    text: str = Query(..., description="The text to convert to speech"),
    voice: str = Query("pf_dora", description="Voice profile to use (e.g.,pf_dora, af_bella, am_adam)")
):
    controller = AudioSynthController()
    def audio_streamer():
        for chunk in controller.generate_audio_chunks(text, voice):
            yield chunk

    return StreamingResponse(audio_streamer(), media_type="audio/wav")
async def update_json(data: dict):
    pass
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)