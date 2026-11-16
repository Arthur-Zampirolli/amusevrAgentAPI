# amusevrAgentAPI

API em FastAPI para processamento de comandos de voz, atualização de XML MultiSEL, síntese de fala e integração com o SensorySynch360 para sugestão de efeitos.

## Requisitos

- Python 3.12+
- Dependências em `requirements.txt`
- (Opcional, conforme uso) Ollama, modelos Whisper/Kokoro e serviço SensorySynch360 acessível

## Instalação

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuração

Crie/ajuste o arquivo `config/.env` com as variáveis necessárias:

```env
# Ollama / agente
OLLAMA_API_URL=http://localhost
OLLAMA_PORT=11434

# Voz / TTS
VOICE=pf_dora

# Servidor
SERVER_ADDRESS=0.0.0.0
SERVER_PORT=8000

# Whisper (transcrição)
OFFLOAD_LEVEL=0
WHISPER_MODEL=base
WHISPER_PRECISION=float16

# SensorySynch360
SENSORYSYNCH_API_URL=127.0.0.1
SENSORYSYNCH_API_PORT=8007
```

> Ajuste os valores conforme o seu ambiente.

## Execução

```bash
source venv/bin/activate
python main.py
```

A API sobe por padrão em `http://0.0.0.0:8000`.

## Endpoints

| Método | Rota | Descrição |
| --- | --- | --- |
| `POST` | `/update-xml` | Atualiza/injeta dados em uma cena do XML (`xml_data`, `new_data`, `scene_id`). |
| `POST` | `/transcribe-audio` | Transcreve um arquivo de áudio (multipart `file`). |
| `POST` | `/process-command` | Transcreve áudio, processa comando com o agente e atualiza o XML (multipart: `scene_id`, `xml_data`, `file`). |
| `GET` | `/to-speech` | Converte texto em áudio WAV (`text`, `voice`). |
| `POST` | `/suggest-effects` | Envia vídeo (base64) ao SensorySynch360 e retorna o último status do job. |
| `GET` | `/get-modules-status` | Consulta status de um job (`user_id=<job_uid>` retornado por `/suggest-effects`). |

### Exemplo: `/suggest-effects`

```json
{
  "modules": ["sunLocalization"],
  "video": "data:video/mp4;base64,AAAA..."
}
```

- Enviar como `POST` com `Content-Type: application/json`.
- `video`: string base64 (com ou sem prefixo `data:<mime>;base64,`), sem caracteres de controle não escapados.
- Campos opcionais: `user_id`, `mime_type`, `modules`.