# AI Talking Avatar MVP

Generate 30-second 720p talking avatar videos from user photos and scripts using AI.

## Overview

This system processes user photos and scripts to create personalized talking avatar videos. The pipeline includes:

1. **Identity Engine**: Creates LoRA models for user identity using Stable Diffusion 1.5
2. **TTS Engine**: Converts text to speech using ElevenLabs API (supports custom voices)
3. **Talking Head Engine**: Generates talking head videos using SadTalker
4. **Product Compositor**: Optionally composites avatar with product images
5. **Video Enhancement**: Applies face restoration, upscaling, smoothing, and color correction
6. **Job Queue**: Async processing using Celery and Redis

## Features

- ✅ Face detection and alignment using InsightFace
- ✅ LoRA training for user identity (SD 1.5)
- ✅ Text-to-speech with ElevenLabs (Turkish support)
- ✅ Custom voice cloning from samples
- ✅ Talking head video generation (SadTalker)
- ✅ Product image composition
- ✅ Video enhancement pipeline (GFPGAN, RealESRGAN)
- ✅ Async job processing with Celery
- ✅ S3 storage integration
- ✅ RESTful API with FastAPI

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  FastAPI    │────▶│   Redis     │
│   Server    │     │   Broker    │
└──────┬──────┘     └──────┬──────┘
       │                    │
       ▼                    ▼
┌─────────────┐     ┌─────────────┐
│  MongoDB   │     │   Celery    │
│  Database   │     │   Workers   │
└─────────────┘     └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Pipeline   │
                    │   Modules    │
                    └─────────────┘
```

## Quick Start

Sıfırdan klonlama ve kurulum için → **[CLEAN_SETUP.md](CLEAN_SETUP.md)** adımlarını izleyin.

---

## Prerequisites

- Python 3.10+
- MongoDB 6+
- Redis 7+
- NVIDIA GPU with CUDA 11.8+ (for workers)
- Docker and Docker Compose (recommended)
- ElevenLabs API key

## Installation

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd user_avatar_LoRa_pipeline_engine
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Initialize database** (creates `lora_avatar` DB and collections if missing)
   ```bash
   docker-compose exec api python -c "from app.api.dependencies import init_db; init_db()"
   ```

### RunPod Deployment (Recommended for GPU)

1. **Create RunPod Pod**
   - Base Image: `pytorch/pytorch:2.1.1-cuda11.8-cudnn8-runtime`
   - Container Disk: Minimum 50GB
   - GPU: RTX 3090 / A100 / A6000 (24GB+ VRAM recommended)

2. **Set Environment Variables** in RunPod template:
   ```
   MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
   MONGODB_DB_NAME=lora_avatar
   REDIS_URL=rediss://default:XXXX@xxx.upstash.io:6379
   CELERY_BROKER_URL=rediss://default:XXXX@xxx.upstash.io:6379
   CELERY_RESULT_BACKEND=rediss://default:XXXX@xxx.upstash.io:6379
   ELEVENLABS_API_KEY=your_key_here
   NGROK_AUTHTOKEN=your_ngrok_token (optional)
   START_CELERY_WORKER=true
   ```

3. **Set Start Command**:
   ```bash
   cd /workspace && git clone https://github.com/YOUR_USERNAME/user_avatar_LoRa_pipeline_engine.git && cd user_avatar_LoRa_pipeline_engine && chmod +x start.sh && ./start.sh
   ```

4. **Expose Ports**: `8000` (API), `4040` (Ngrok web UI)

5. **After startup**, check logs for Ngrok public URL:
   ```bash
   tail -f /workspace/ngrok.log
   # Or visit: http://localhost:4040
   ```

See `RUNPOD_SETUP.md` for detailed RunPod setup instructions.

### Manual Installation

1. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up MongoDB and Redis**
   - Install and start MongoDB; set `MONGODB_URI` in `.env` (e.g. `mongodb://localhost:27017`)
   - Install and start Redis

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env: set MONGODB_URI and MONGODB_DB_NAME (default: lora_avatar)
   ```

4. **Initialize database** (creates database `lora_avatar` and collections `users`, `jobs` if missing)
   ```bash
   python -c "from app.api.dependencies import init_db; init_db()"
   ```

5. **Start API server**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

6. **Start Celery worker** (in separate terminal)
   ```bash
   celery -A app.queue.celery_app worker --loglevel=info --queues=gpu,default
   ```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options. Key variables:

- `MONGODB_URI`: MongoDB connection URL (e.g. `mongodb://localhost:27017` or Atlas URI)
- `MONGODB_DB_NAME`: Database name (default: `lora_avatar`); collections `users` and `jobs` are created on init
- `REDIS_URL`: Redis connection string
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key
- `AWS_ACCESS_KEY_ID`: AWS S3 access key (optional)
- `AWS_SECRET_ACCESS_KEY`: AWS S3 secret key (optional)
- `S3_BUCKET_NAME`: S3 bucket name (optional)

### File Storage Paths

Default paths (configurable via environment variables):
- `/datasets/{user_id}/`: Processed training images
- `/lora_storage/`: Trained LoRA models
- `/audio/`: Generated audio files
- `/video_raw/`: Raw talking head videos
- `/video_final/`: Final enhanced videos

## API Endpoints

### Upload Photos
```http
POST /api/v1/upload-photos
Content-Type: multipart/form-data

user_id: string
photos: file[]
```

### Train Identity
```http
POST /api/v1/train-identity
Content-Type: application/json

{
  "user_id": "user_123"
}
```

### Check Training Status
```http
GET /api/v1/training-status/{user_id}
```

### Generate Video
```http
POST /api/v1/generate-video
Content-Type: application/json

{
  "user_id": "user_123",
  "script_text": "Merhaba, bu bir test mesajıdır.",
  "product_image": "base64_encoded_image" (optional),
  "voice_sample": "base64_encoded_audio" (optional)
}
```

### Check Job Status
```http
GET /api/v1/job-status/{job_id}
```

### Download Video
```http
GET /api/v1/video/{job_id}
```

## Usage Example

### Python Client

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 1. Upload photos
with open("photo1.jpg", "rb") as f1, open("photo2.jpg", "rb") as f2:
    files = {"photos": [f1, f2]}
    data = {"user_id": "user_123"}
    response = requests.post(f"{BASE_URL}/upload-photos", files=files, data=data)
    print(response.json())

# 2. Train identity
response = requests.post(
    f"{BASE_URL}/train-identity",
    json={"user_id": "user_123"}
)
print(response.json())

# 3. Check training status
response = requests.get(f"{BASE_URL}/training-status/user_123")
print(response.json())

# 4. Generate video
response = requests.post(
    f"{BASE_URL}/generate-video",
    json={
        "user_id": "user_123",
        "script_text": "Merhaba, bu bir test mesajıdır."
    }
)
job = response.json()
print(f"Job ID: {job['job_id']}")

# 5. Check job status
response = requests.get(f"{BASE_URL}/job-status/{job['job_id']}")
print(response.json())

# 6. Download video
response = requests.get(f"{BASE_URL}/video/{job['job_id']}")
with open("output.mp4", "wb") as f:
    f.write(response.content)
```

### cURL Example

```bash
# Upload photos
curl -X POST "http://localhost:8000/api/v1/upload-photos" \
  -F "user_id=user_123" \
  -F "photos=@photo1.jpg" \
  -F "photos=@photo2.jpg"

# Train identity
curl -X POST "http://localhost:8000/api/v1/train-identity" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123"}'

# Generate video
curl -X POST "http://localhost:8000/api/v1/generate-video" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "script_text": "Merhaba, bu bir test mesajıdır."
  }'
```

## Pipeline Flow

1. **Photo Upload**: User uploads photos → stored in `/datasets/{user_id}/uploads/`
2. **Preprocessing**: Face detection, alignment, cropping to 512x512
3. **Caption Generation**: Auto-generate captions for LoRA training
4. **LoRA Training**: Train Stable Diffusion LoRA model (async)
5. **TTS Generation**: Convert script to audio using ElevenLabs
6. **Talking Head**: Generate talking head video from face image + audio
7. **Product Composition**: (Optional) Compose with product image
8. **Enhancement**: Face restoration → Upscaling → Smoothing → Color correction
9. **Upload**: Upload final video to S3 (optional)
10. **Delivery**: Return download URL

## Module Details

### Identity Engine
- **Preprocessor**: InsightFace for face detection and alignment
- **Caption Generator**: Auto-generates training captions
- **LoRA Trainer**: Trains SD 1.5 LoRA models (rank=8, epochs=12)

### TTS Engine
- **ElevenLabs Client**: API integration for TTS
- **Voice Manager**: Custom voice creation and management
- **Fallback**: Default Turkish voice if custom voice fails

### Talking Head Engine
- **SadTalker Wrapper**: Integration with SadTalker for video generation
- **Input**: 512x512 face image + WAV audio
- **Output**: 512x512 talking head video

### Product Compositor
- **Background Removal**: Uses rembg or OpenCV-based segmentation
- **Layout**: Avatar left (60%), Product right (40%)
- **Output**: Composed video at target resolution

### Video Enhancement
- **Face Restoration**: GFPGAN for face quality improvement
- **Upscaling**: RealESRGAN to 720p (1280x720)
- **Temporal Smoothing**: Frame interpolation for smooth motion
- **Color Correction**: Brightness, contrast, saturation, gamma adjustment

## Development

### Project Structure

```
/app
  /identity_engine      # LoRA training modules
  /tts_engine           # ElevenLabs TTS integration
  /talking_head         # SadTalker wrapper
  /compositor           # Product composition
  /enhancer             # Video enhancement
  /queue                # Celery tasks
  /api                  # FastAPI routes and models
  /database             # SQLAlchemy models
  /storage              # S3 client
  /config               # Configuration management
main.py                 # FastAPI app entry point
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Quality

```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## Troubleshooting

### GPU Not Available
- Ensure NVIDIA drivers are installed
- Check CUDA installation: `nvidia-smi`
- For Docker: Use `nvidia-docker` or Docker with GPU support

### SadTalker Not Found
- Set `SADTALKER_PATH` environment variable
- Or clone SadTalker repository and update path in code

### ElevenLabs API Errors
- Verify API key is correct
- Check API quota/limits
- System will fallback to default Turkish voice on failure

### Database Connection Issues
- Verify MongoDB is running
- Check `MONGODB_URI` in `.env` (e.g. `mongodb://localhost:27017`)
- Run `init_db()` to create database `lora_avatar` and collections if missing

## Limitations

- Maximum script length: 1000 characters
- Maximum video duration: 30 seconds
- One avatar per user (LoRA model)
- Requires GPU for optimal performance
- ElevenLabs API costs apply per character

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Support

[Add support contact information here]


Redis
# 1. Redis kur
apt-get update && apt-get install -y redis-server

# 2. Arka planda başlat
redis-server --daemonize yes

# 3. Kontrol et
redis-cli ping
# Cevap: PONG

# Celery worker'ı başlat (gpu + default kuyruklarını dinlesin)
celery -A app.queue.celery_app worker --loglevel=info --queues=gpu,default,celery --concurrency=1


Seçenek 1: SadTalker'ı RunPod'da kurun (önerilen)
RunPod terminalinde:
requirem
cd /workspacegit clone https://github.com/OpenTalker/SadTalker.gitcd SadTalker# Bağımlılıkları yüklepip install -r requirements.txt# Checkpoint'leri indir (gerekirse)# mkdir -p checkpoints# wget -O checkpoints/checkpoint.tar [URL]