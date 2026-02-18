#!/bin/bash

# RunPod Startup Script for AI Talking Avatar MVP
# Bu script RunPod container başlatıldığında otomatik çalışır

set -e  # Hata durumunda dur (kritik komutlar için)

echo "🚀 AI Talking Avatar MVP - RunPod Startup Script"
echo "=================================================="

# Proje dizini kontrolü
PROJECT_DIR="/workspace/user_avatar_LoRa_pipeline_engine"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "⚠️  Proje dizini bulunamadı: $PROJECT_DIR"
    echo "💡 RunPod Start Command'da git clone komutunu kullandığınızdan emin olun"
    echo "💡 Veya projeyi manuel olarak /workspace/user_avatar_LoRa_pipeline_engine'e kopyalayın"
    exit 1
fi
cd "$PROJECT_DIR" || exit 1
echo "📁 Proje dizini: $PROJECT_DIR"

# Python kontrolü
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 bulunamadı!"
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 1. Ngrok kurulumu
echo ""
echo "📦 Ngrok kuruluyor..."
if ! command -v ngrok &> /dev/null; then
    curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
        sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
        echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
        sudo tee /etc/apt/sources.list.d/ngrok.list && \
        sudo apt update && \
        sudo apt install ngrok -y || {
            echo "⚠️  Ngrok kurulumu başarısız, alternatif yöntem deneniyor..."
            wget https://bin.equinox.io/c/bNyj1mQV2kg/ngrok-v3-stable-linux-amd64.tgz -O /tmp/ngrok.tgz
            tar -xzf /tmp/ngrok.tgz -C /tmp
            sudo mv /tmp/ngrok /usr/local/bin/ngrok
            sudo chmod +x /usr/local/bin/ngrok
        }
    echo "✅ Ngrok kuruldu"
else
    echo "✅ Ngrok zaten kurulu"
fi

# 2. Python bağımlılıkları
echo ""
echo "📦 Python bağımlılıkları kontrol ediliyor..."
if [ ! -f ".installed" ]; then
    echo "İlk kurulum yapılıyor..."
    
    set +e  # Hata kontrolünü geçici kapat
    
    # pip'i güncelle
    pip install --upgrade pip --quiet
    
    # NumPy uyumluluğu için önce numpy yükle
    echo "  → NumPy yükleniyor..."
    pip install "numpy<2.0,>=1.26.0" --quiet || {
        echo "⚠️  NumPy yükleme hatası, devam ediliyor..."
    }
    
    # Diğer paketleri yükle (numpy hariç - zaten yüklü)
    echo "  → Diğer paketler yükleniyor..."
    pip install -r requirements.txt --quiet || {
        echo "⚠️  Bazı paketler yüklenemedi, devam ediliyor..."
    }
    
    # opencv-python'ı numpy ile uyumlu hale getir
    echo "  → OpenCV yeniden yükleniyor..."
    pip install --force-reinstall opencv-python==4.8.1.78 --quiet || {
        echo "⚠️  OpenCV yükleme hatası, devam ediliyor..."
    }
    
    set -e  # Tekrar aç
    
    touch .installed
    echo "✅ Bağımlılıklar yüklendi (bazı uyarılar normal olabilir)"
else
    echo "✅ Bağımlılıklar zaten yüklü"
fi

# 3. .env dosyası kontrolü
echo ""
echo "🔧 .env dosyası kontrol ediliyor..."
if [ ! -f ".env" ]; then
    echo "⚠️  .env dosyası bulunamadı! .env.example'dan kopyalanıyor..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "⚠️  LÜTFEN .env DOSYASINI DÜZENLEYİN: MongoDB, Redis, ElevenLabs bilgilerini girin!"
    else
        echo "❌ .env.example da bulunamadı!"
        exit 1
    fi
fi

# 4. Gerekli klasörleri oluştur
echo ""
echo "📁 Klasörler oluşturuluyor..."
mkdir -p /workspace/datasets
mkdir -p /workspace/lora_storage
mkdir -p /workspace/audio
mkdir -p /workspace/video_raw
mkdir -p /workspace/video_final
echo "✅ Klasörler hazır"

# 5. Veritabanını başlat
echo ""
echo "🗄️  Veritabanı başlatılıyor..."
set +e  # Geçici olarak hata kontrolünü kapat
python -c "from app.api.dependencies import init_db; init_db()" 2>&1
DB_INIT_STATUS=$?
set -e  # Tekrar aç
if [ $DB_INIT_STATUS -ne 0 ]; then
    echo "⚠️  Veritabanı başlatma hatası (MongoDB bağlantısını kontrol edin)"
    echo "💡 API çalışmaya devam edecek ama veritabanı işlemleri başarısız olabilir"
fi

# 6. Ngrok token kontrolü (opsiyonel - environment variable'dan)
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo ""
    echo "⚠️  NGROK_AUTHTOKEN environment variable bulunamadı"
    echo "💡 Ngrok'u token olmadan başlatıyoruz (ücretsiz plan)"
else
    ngrok config add-authtoken "$NGROK_AUTHTOKEN"
    echo "✅ Ngrok token ayarlandı"
fi

# 7. Eski process'leri temizle
echo ""
echo "🧹 Eski process'ler temizleniyor..."
pkill -f uvicorn || true
pkill -f ngrok || true
sleep 2

# 8. API'yi başlat (arka planda)
echo ""
echo "🌐 API başlatılıyor..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /workspace/api.log 2>&1 &
API_PID=$!
sleep 3

# API'nin çalıştığını kontrol et
if ps -p $API_PID > /dev/null; then
    echo "✅ API başlatıldı (PID: $API_PID)"
else
    echo "❌ API başlatılamadı! Logları kontrol edin:"
    tail -20 /workspace/api.log
    exit 1
fi

# 9. Ngrok'u başlat (arka planda)
echo ""
echo "🌍 Ngrok başlatılıyor..."
nohup ngrok http 8000 --log=stdout > /workspace/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 5

# Ngrok URL'ini al
echo ""
echo "🔍 Ngrok URL'i alınıyor..."
NGROK_URL=""
for i in {1..15}; do
    sleep 2
    NGROK_RESPONSE=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null)
    if [ ! -z "$NGROK_RESPONSE" ]; then
        NGROK_URL=$(echo "$NGROK_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
        if [ ! -z "$NGROK_URL" ]; then
            break
        fi
        # Alternatif: grep ile
        NGROK_URL=$(echo "$NGROK_RESPONSE" | grep -o '"public_url":"https://[^"]*' | head -1 | cut -d'"' -f4)
        if [ ! -z "$NGROK_URL" ]; then
            break
        fi
    fi
done

echo ""
echo "=================================================="
echo "✅ BAŞLATMA TAMAMLANDI!"
echo "=================================================="
echo ""

if [ ! -z "$NGROK_URL" ]; then
    echo "🌐 Public URL (Ngrok): $NGROK_URL"
    echo "📚 API Docs: $NGROK_URL/docs"
    echo "💚 Health Check: $NGROK_URL/health"
else
    echo "⚠️  Ngrok URL'i alınamadı"
    echo "💡 Ngrok web UI: http://localhost:4040"
    echo "💡 API yerel: http://localhost:8000"
fi

echo ""
echo "📊 Loglar:"
echo "   API: tail -f /workspace/api.log"
echo "   Ngrok: tail -f /workspace/ngrok.log"
echo ""
echo "🔍 Ngrok URL'ini manuel kontrol:"
echo "   curl http://localhost:4040/api/tunnels | python3 -m json.tool"
echo ""
echo "🛑 Durdurma:"
echo "   pkill -f uvicorn && pkill -f ngrok"
echo ""

# 10. (Opsiyonel) Celery Worker başlat
if [ "$START_CELERY_WORKER" = "true" ]; then
    echo ""
    echo "⚙️  Celery Worker başlatılıyor..."
    nohup celery -A app.queue.celery_app worker --loglevel=info --queues=gpu,default > /workspace/celery.log 2>&1 &
    echo "✅ Celery Worker başlatıldı"
fi

echo ""
echo "✅ Startup script tamamlandı!"
echo ""

# Logları göster (opsiyonel)
if [ "$SHOW_LOGS" = "true" ]; then
    tail -f /workspace/api.log
fi
