import io
import soundfile as sf
from fastapi.responses import StreamingResponse

from kokoro import KPipeline
class AudioSynthController:
    def __init__(self):
        pass

    @staticmethod
    def get_kokoro_lang_code(output_lang):
        kokoro_lang_codes = {
            "en-us": "a",
            "en-uk": "b",
            "es": "e",
            "fr": "f",
            "hi": "h",
            "ja": "j",
            "pt-br": "p",
            "zh": "z",
            "zt": "z",
        }
        if output_lang not in kokoro_lang_codes:
            raise ValueError("Invalid output language.")
        return kokoro_lang_codes[output_lang]

    def build_tts_pipeline(self, output_lang, device):


        return KPipeline(
            repo_id="hexgrad/Kokoro-82M",
            lang_code=self.get_kokoro_lang_code(output_lang),
            device=device,
        )

    def generate_audio_chunks(self, text: str, voice: str):

        # generator = pipeline(text, voice=voice, speed=1.0, lang_code=get_kokoro_lang_code("pt-br"), split_pattern=r'\n+')
        pipeline = KPipeline(lang_code=self.get_kokoro_lang_code("pt-br"), device="cuda", repo_id="hexgrad/Kokoro-82M")
        generator = pipeline(text=text, voice=voice, speed=1.0, split_pattern=r'\n+')
        for _, _, audio in generator:
            bytes_io = io.BytesIO()

            sf.write(bytes_io, audio, 24000, format='WAV', subtype='PCM_16')

            yield bytes_io.getvalue()
    @staticmethod
    async def synth_audio(text, voice):
        controller = AudioSynthController()
        def audio_streamer():
            for chunk in controller.generate_audio_chunks(text, voice):
                yield chunk

        return StreamingResponse(audio_streamer(), media_type="audio/wav")