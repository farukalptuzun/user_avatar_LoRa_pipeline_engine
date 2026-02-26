# Temiz Kurulum Rehberi

Bu rehber projeyi sıfırdan klonlayıp çalıştırma adımlarını anlatır.

---

## Gereksinimler

- **Python** 3.10+
- **MongoDB** 6+ (yerel veya MongoDB Atlas)
- **Redis** 7+ (yerel veya Upstash)
- **NVIDIA GPU** CUDA 11.8+ (worker için önerilir)
- **ElevenLabs API** anahtarı

---

## 1. Projeyi Klonla

```bash
git clone https://github.com/farukalptuzun/user_avatar_LoRa_pipeline_engine.git
cd user_avatar_LoRa_pipeline_engine
apt update && apt install -y nano
```

---

## 2. Ortam Değişkenlerini Ayarla

```bash
cp .env.example .env
```

`.env` dosyasını düzenle ve şu alanları doldur:

| Değişken | Açıklama | Örnek |
|----------|----------|-------|
| `MONGODB_URI` | MongoDB bağlantı adresi | `mongodb://localhost:27017` veya Atlas URI |
| `MONGODB_DB_NAME` | Veritabanı adı | `lora_avatar` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery sonuç backend | `redis://localhost:6379/0` |
| `ELEVENLABS_API_KEY` | ElevenLabs API anahtarı | [elevenlabs.io](https://elevenlabs.io) |

---

## 3. Python Bağımlılıklarını Kur

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. Çalıştırma

### Yöntem A: RunPod (GPU ile — Önerilen)

RunPod template'inde **Start Command** olarak:

```bash
cd /workspace && git clone https://github.com/farukalptuzun/user_avatar_LoRa_pipeline_engine.git && cd user_avatar_LoRa_pipeline_engine && chmod +x start.sh && START_CELERY_WORKER=true ./start.sh
```

`start.sh` şunları yapar:
- Ngrok kurulumu
- Python bağımlılıkları
- SadTalker klonlama (`/workspace/SadTalker`)
- SadTalker checkpoint indirme
- API arka planda
- Ngrok arka planda
- **Celery worker ön planda** (loglar terminalde görünür)

**RunPod ortam değişkenleri** (template'e ekle):
```
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DB_NAME=lora_avatar
REDIS_URL=rediss://default:XXX@xxx.upstash.io:6379
CELERY_BROKER_URL=rediss://default:XXX@xxx.upstash.io:6379
CELERY_RESULT_BACKEND=rediss://default:XXX@xxx.upstash.io:6379
ELEVENLABS_API_KEY=your_key
NGROK_AUTHTOKEN=your_ngrok_token
START_CELERY_WORKER=true
```

---

### Yöntem B: Lokal (Manuel)

#### 4.1 MongoDB ve Redis çalışıyor olmalı

```bash
# MongoDB (örnek: macOS Homebrew)
brew services start mongodb-community

# Redis
brew services start redis
# veya: redis-server --daemonize yes
```

#### 4.2 Veritabanını başlat

```bash
python -c "from app.api.dependencies import init_db; init_db()"
```

#### 4.3 API’yi başlat (Terminal 1)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### 4.4 Celery Worker’ı başlat (Terminal 2)

```bash
celery -A app.queue.celery_app worker --loglevel=info --queues=gpu,default
```

#### 4.5 SadTalker (opsiyonel — video üretimi için)

SadTalker otomatik değilse:

```bash
cd /workspace  # veya uygun bir dizin
git clone https://github.com/OpenTalker/SadTalker.git
cd SadTalker
bash scripts/download_models.sh  # checkpoint'leri indir
```

`.env` veya ortam değişkenleri:
```
SADTALKER_PATH=/workspace/SadTalker
SADTALKER_CHECKPOINT_PATH=/workspace/SadTalker/checkpoints
```

---

## 5. Çalıştığını Kontrol Et

```bash
# API sağlık kontrolü
curl http://localhost:8000/health

# API dokümantasyonu
# Tarayıcıda: http://localhost:8000/docs
```

---

## 6. Hızlı Özet (RunPod)

```bash
# 1. Klonla
cd /workspace
git clone https://github.com/YOUR_USERNAME/user_avatar_LoRa_pipeline_engine.git
cd user_avatar_LoRa_pipeline_engine

# 2. .env oluştur (veya ortam değişkenleri template'te tanımlı olsun)
cp .env.example .env
# .env dosyasını düzenle

# 3. Çalıştır (SadTalker + API + Worker tek seferde)
chmod +x start.sh
START_CELERY_WORKER=true ./start.sh
```

---

## Sık Karşılaşılan Sorunlar

| Sorun | Çözüm |
|-------|-------|
| `MONGODB_URI` hatası | MongoDB çalışıyor mu kontrol et; URI’yi `.env` içinde doğrula |
| `redis connection refused` | Redis servisini başlat |
| SadTalker bulunamadı | `SADTALKER_PATH` ve checkpoint path’ini kontrol et |
| CUDA/GPU hatası | `nvidia-smi` ile sürücü ve CUDA sürümünü kontrol et |
