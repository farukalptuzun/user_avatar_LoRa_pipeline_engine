# RunPod Kurulum Rehberi

## RunPod Template Ayarları

### 1. Container Image
- **Base Image**: `pytorch/pytorch:2.1.1-cuda11.8-cudnn8-runtime`
- veya `nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04`

### 2. Container Disk
- **Minimum**: 50GB (LoRA modelleri ve videolar için)

### 3. Environment Variables
RunPod template'inde şu environment variable'ları ekle:

```
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=lora_avatar
REDIS_URL=rediss://default:XXXX@xxx.upstash.io:6379
CELERY_BROKER_URL=rediss://default:XXXX@xxx.upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:XXXX@xxx.upstash.io:6379
ELEVENLABS_API_KEY=your_key_here
NGROK_AUTHTOKEN=your_ngrok_token (opsiyonel)
START_CELERY_WORKER=true (opsiyonel)
```

### 4. Start Command
```bash
cd /workspace && git clone https://github.com/KULLANICI/user_avatar_LoRa_pipeline_engine.git && cd user_avatar_LoRa_pipeline_engine && chmod +x start.sh && ./start.sh
```

veya eğer projeyi zaten `/workspace`'e yüklediysen:

```bash
cd /workspace/user_avatar_LoRa_pipeline_engine && chmod +x start.sh && ./start.sh
```

### 5. Exposed Ports
- **Port**: `8000` (API için)
- **Port**: `4040` (Ngrok web interface için)

## Ngrok Token Alma (Opsiyonel)

1. [ngrok.com](https://ngrok.com) hesabı oluştur
2. Dashboard'dan authtoken'ı kopyala
3. RunPod environment variable'larına ekle: `NGROK_AUTHTOKEN=your_token`

**Not**: Token olmadan da çalışır ama ücretsiz plan limitleri var.

## Manuel Başlatma

Eğer startup script çalışmazsa, terminalden:

```bash
cd /workspace/user_avatar_LoRa_pipeline_engine
chmod +x start.sh
./start.sh
```

## Log Kontrolü

```bash
# API logları
tail -f /workspace/api.log

# Ngrok logları
tail -f /workspace/ngrok.log

# Celery logları (eğer başlatıldıysa)
tail -f /workspace/celery.log
```

## Ngrok URL'ini Bulma

```bash
# Ngrok web interface
curl http://localhost:4040/api/tunnels | python3 -m json.tool

# Veya browser'da
http://localhost:4040
```

## Durdurma

```bash
pkill -f uvicorn
pkill -f ngrok
pkill -f celery
```

## Sorun Giderme

### API başlamıyor
```bash
# Logları kontrol et
tail -50 /workspace/api.log

# Manuel başlat
cd /workspace/user_avatar_LoRa_pipeline_engine
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Ngrok başlamıyor
```bash
# Ngrok loglarını kontrol et
tail -50 /workspace/ngrok.log

# Manuel başlat
ngrok http 8000
```

### MongoDB bağlantı hatası
- `.env` dosyasındaki `MONGODB_URI`'yi kontrol et
- MongoDB Atlas'ta IP whitelist'e RunPod IP'sini ekle (veya `0.0.0.0/0`)

### Port zaten kullanılıyor
```bash
# Port 8000'i kullanan process'i bul ve durdur
lsof -ti:8000 | xargs kill
```
