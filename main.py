import base64
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
import uvicorn

from controller.AudioSynthController import AudioSynthController
from controller.CommandController import CommandController
from controller.SensorySynchController import SensorySynchController
from controller.XMLController import XMLController
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from config.helpers.ConfigHelper import ConfigHelper
import time
import asyncio
import os

dotenv_path = Path('config/.env')
load_dotenv(dotenv_path=dotenv_path)
app = FastAPI()

#rotear a chamada de envio do xml

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
@app.post("/transcribe-audio")
async def transcribe_audio(file: UploadFile = File(...)):
    controller = CommandController(ConfigHelper())
    return await controller.transcribe_audio(file)

@app.post("/process-command")
async def process_command(scene_id: str = Form(...),xml_data: str = Form(...), file: UploadFile = File(...)):
    try:
        print(f"Received XML: {xml_data}")
        #scene_id = data["scene_id"]
        controller = CommandController(ConfigHelper())
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
        res["audio"] = audio_base64
        return {
            'response': res,
        }
    except Exception as e:
        return {"error": str(e)}
@app.get("/to-speech")
async def to_speech(
    text: str = Query(..., description="The text to convert to speech"),
    voice: str = Query("pf_dora", description="Voice profile to use (e.g.,pf_dora, af_bella, am_adam)")
):
    controller = AudioSynthController()
    def audio_streamer():
        for chunk in controller.generate_audio_chunks(text, voice):
            yield chunk

    return StreamingResponse(audio_streamer(), media_type="audio/wav")
@app.post("/suggest-effects")
async def suggest_effects(data: dict = Body(...)):
    video_data = data.get("video")
    if not isinstance(video_data, str) or not video_data:
        raise HTTPException(status_code=400, detail="Campo 'video' (base64) é obrigatório")

    mime_type = data.get("mime_type")
    if video_data.startswith("data:"):
        header, _, encoded = video_data.partition(",")
        if not encoded:
            raise HTTPException(status_code=400, detail="Formato de data URL inválido em 'video'")
        if not mime_type and ":" in header and ";" in header:
            mime_type = header.split(":", 1)[1].split(";", 1)[0]
        video_data = encoded

    try:
        video_bytes = base64.b64decode(video_data, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Campo 'video' não é um base64 válido")

    controller = SensorySynchController(ConfigHelper())
    res = await controller.upload_video(
        video_bytes=video_bytes,
        modules=data.get("modules"),
        user_id=data.get("user_id"),
        mime_type=mime_type,
    )
    job_uid = res.get("job_uid")
    print(f"Job UID: {job_uid}")

    get_modules_status = {}
    max_tentativas = int(os.getenv("MAX_ATTEMPTS"))  # Ex: 30 * 10s = 5 minutos máximo de espera

    for tentativa in range(max_tentativas):
        try:
            get_modules_status = await controller.get_modules_status(job_uid=job_uid)
            print(f"[{tentativa + 1}/{max_tentativas}] Modules Status: {get_modules_status}")

            # Garante que o dicionário não está vazio e verifica se TODOS os módulos têm status == '100'
            if get_modules_status and all(
                isinstance(modulo, dict) and str(modulo.get("status")) == "100"
                for modulo in get_modules_status.values()
            ):
                print("Todos os módulos concluídos com status 100!")
                break

        except Exception as e:
            print(f"Error fetching modules status: {e}")
            raise HTTPException(status_code=502, detail=f"Erro ao consultar status dos módulos: {e}")

        await asyncio.sleep(10)  # Não bloqueia o event loop do FastAPI
    else:
        raise HTTPException(status_code=504, detail="Tempo limite excedido aguardando processamento dos módulos")

    return {
        "response": res,
        "modules_status": get_modules_status,
        "xml_data": controller.parse_to_xml(get_modules_status)
    }
@app.get("/get-modules-status")
async def get_modules_status(
    job_uid: str = Query(..., description="job_uid retornado por /suggest-effects")
):
    controller = SensorySynchController(ConfigHelper())
    return await controller.get_modules_status(job_uid=job_uid)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)