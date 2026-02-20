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
    # RunPod'da sudo olmayabilir, root kullanıcı kontrolü
    if [ "$EUID" -eq 0 ] || [ "$(id -u)" -eq 0 ]; then
        SUDO_CMD=""
    else
        # sudo var mı kontrol et
        if command -v sudo &> /dev/null; then
            SUDO_CMD="sudo"
        else
            SUDO_CMD=""
        fi
    fi
    
    # Önce apt ile deneme (Debian/Ubuntu)
    if command -v apt-get &> /dev/null; then
        set +e
        # Güncel repository (bookworm)
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
            $SUDO_CMD tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null 2>&1 && \
            echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" | \
            $SUDO_CMD tee /etc/apt/sources.list.d/ngrok.list >/dev/null 2>&1 && \
            $SUDO_CMD apt update >/dev/null 2>&1 && \
            $SUDO_CMD apt install ngrok -y >/dev/null 2>&1
        APT_STATUS=$?
        set -e
        
        if [ $APT_STATUS -eq 0 ] && command -v ngrok &> /dev/null; then
            echo "✅ Ngrok apt ile kuruldu"
        else
            echo "⚠️  Apt kurulumu başarısız, binary indirme deneniyor..."
            # Binary indirme (güncel URL - .tgz formatı)
            wget -q "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" -O /tmp/ngrok.tgz 2>/dev/null || \
            curl -L "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" -o /tmp/ngrok.tgz 2>/dev/null
            
            if [ -f /tmp/ngrok.tgz ]; then
                # tar ile çıkar (.tgz formatı)
                tar -xzf /tmp/ngrok.tgz -C /tmp 2>/dev/null
                if [ -f /tmp/ngrok ]; then
                    $SUDO_CMD mv /tmp/ngrok /usr/local/bin/ngrok 2>/dev/null || mv /tmp/ngrok /usr/local/bin/ngrok
                    $SUDO_CMD chmod +x /usr/local/bin/ngrok 2>/dev/null || chmod +x /usr/local/bin/ngrok
                    rm -f /tmp/ngrok.tgz
                    echo "✅ Ngrok binary ile kuruldu"
                else
                    echo "⚠️  Ngrok binary çıkarılamadı"
                fi
            else
                echo "⚠️  Ngrok indirilemedi, manuel kurulum gerekebilir"
                echo "💡 Alternatif: https://ngrok.com/download adresinden indirin"
            fi
        fi
    else
        # Apt yoksa direkt binary indirme
        echo "⚠️  Apt bulunamadı, binary indirme deneniyor..."
        wget -q "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" -O /tmp/ngrok.tgz 2>/dev/null || \
        curl -L "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz" -o /tmp/ngrok.tgz 2>/dev/null
        
        if [ -f /tmp/ngrok.tgz ]; then
            # tar ile çıkar (.tgz formatı)
            tar -xzf /tmp/ngrok.tgz -C /tmp 2>/dev/null
            if [ -f /tmp/ngrok ]; then
                mv /tmp/ngrok /usr/local/bin/ngrok 2>/dev/null || cp /tmp/ngrok /usr/local/bin/ngrok
                chmod +x /usr/local/bin/ngrok
                rm -f /tmp/ngrok.tgz
                echo "✅ Ngrok binary ile kuruldu"
            else
                echo "⚠️  Ngrok binary çıkarılamadı"
            fi
        else
            echo "⚠️  Ngrok indirilemedi"
        fi
    fi
    
    # Son kontrol
    if command -v ngrok &> /dev/null; then
        echo "✅ Ngrok hazır: $(ngrok version 2>/dev/null || echo 'kurulu')"
    else
        echo "❌ Ngrok kurulamadı! API çalışacak ama public URL olmayacak"
    fi
else
    echo "✅ Ngrok zaten kurulu: $(ngrok version 2>/dev/null || echo 'kurulu')"
fi

# 2. Python bağımlılıkları
echo ""
echo "📦 Python bağımlılıkları kontrol ediliyor..."
if [ ! -f ".installed" ]; then
    echo "İlk kurulum yapılıyor..."
    
    set +e  # Hata kontrolünü geçici kapat
    
    # pip'i güncelle
    pip install --upgrade pip --quiet
    
    # NumPy uyumluluğu için önce numpy'yi düşür (OpenCV için)
    echo "  → NumPy düşürülüyor (OpenCV uyumluluğu için)..."
    pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet || {
        echo "⚠️  NumPy düşürme hatası, devam ediliyor..."
    }
    
    # NumPy versiyonunu kontrol et
    NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "")
    echo "  → NumPy versiyonu: $NUMPY_VERSION"
    
    # Diğer paketleri yükle
    echo "  → Diğer paketler yükleniyor..."
    pip install -r requirements.txt --quiet || {
        echo "⚠️  Bazı paketler yüklenemedi, devam ediliyor..."
    }
    
    # opencv-python'ı numpy ile uyumlu hale getir (NumPy'yı koruyarak)
    echo "  → OpenCV yeniden yükleniyor (NumPy korunuyor)..."
    # Önce NumPy'yi sabitle
    pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet
    # OpenCV'yi --no-deps ile yükle (NumPy dependency'sini yok say)
    pip install --force-reinstall --no-deps opencv-python==4.8.1.78 --quiet || {
        echo "⚠️  OpenCV yükleme hatası, normal yükleme deneniyor..."
        pip install --force-reinstall opencv-python==4.8.1.78 --quiet
        # Eğer NumPy yine yükseldiyse tekrar düşür
        pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet
    }
    
    # Test: OpenCV import edilebiliyor mu?
    echo "  → OpenCV test ediliyor..."
    python3 -c "import cv2; import numpy; print(f'✅ OpenCV {cv2.__version__} ve NumPy {numpy.__version__} uyumlu')" 2>/dev/null || {
        echo "⚠️  OpenCV import hatası, NumPy yeniden düşürülüyor..."
        pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet
        pip install --force-reinstall --no-deps opencv-python==4.8.1.78 --quiet
        pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet
    }
    
    set -e  # Tekrar aç
    
    touch .installed
    echo "✅ Bağımlılıklar yüklendi (bazı uyarılar normal olabilir)"
else
    echo "✅ Bağımlılıklar zaten yüklü"
    # OpenCV/NumPy uyumluluğunu kontrol et ve düzelt
    set +e
    python3 -c "import cv2; import numpy" 2>/dev/null
    CV2_STATUS=$?
    set -e
    if [ $CV2_STATUS -ne 0 ]; then
        echo "⚠️  OpenCV/NumPy uyumsuzluğu tespit edildi, düzeltiliyor..."
        pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet
        pip install --force-reinstall --no-deps opencv-python==4.8.1.78 --quiet
        pip install "numpy<2.0,>=1.26.0" --force-reinstall --quiet
        echo "✅ NumPy/OpenCV düzeltildi"
    fi
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

# 4. SadTalker kurulumu (/workspace içinde)
echo ""
echo "🎬 SadTalker kuruluyor..."
SADTALKER_DIR="/workspace/SadTalker"
if [ ! -d "$SADTALKER_DIR" ]; then
    echo "  → SadTalker klonlanıyor..."
    cd /workspace
    git clone https://github.com/OpenTalker/SadTalker.git
    cd "$PROJECT_DIR" || exit 1
    echo "✅ SadTalker klonlandı: $SADTALKER_DIR"
else
    echo "✅ SadTalker zaten mevcut: $SADTALKER_DIR"
fi

# SadTalker Python bağımlılıkları (ana projeyle çakışmayanlar)
if [ -f "$SADTALKER_DIR/requirements.txt" ]; then
    echo "  → SadTalker bağımlılıkları yükleniyor..."
    set +e
    pip install -q face_alignment imageio-ffmpeg basicsr facexlib gfpgan av safetensors kornia yacs librosa 2>/dev/null || true
    set -e
fi

# SadTalker checkpoint'leri
SADTALKER_CHECKPOINTS="$SADTALKER_DIR/checkpoints"
if [ ! -f "$SADTALKER_CHECKPOINTS/SadTalker_V0.0.2_256.safetensors" ] && [ ! -f "$SADTALKER_CHECKPOINTS/epoch_20.pth" ]; then
    echo "  → SadTalker checkpoint'leri indiriliyor..."
    cd "$SADTALKER_DIR"
    mkdir -p ./checkpoints
    set +e
    # OpenTalker v0.0.2-rc checkpoint'leri
    wget -q -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00109-model.pth.tar -O ./checkpoints/mapping_00109-model.pth.tar
    wget -q -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00229-model.pth.tar -O ./checkpoints/mapping_00229-model.pth.tar
    wget -q -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors -O ./checkpoints/SadTalker_V0.0.2_256.safetensors
    wget -q -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors -O ./checkpoints/SadTalker_V0.0.2_512.safetensors
    # GFPGAN enhancer ağırlıkları
    mkdir -p ./gfpgan/weights
    wget -q -nc https://github.com/xinntao/facexlib/releases/download/v0.1.0/alignment_WFLW_4HG.pth -O ./gfpgan/weights/alignment_WFLW_4HG.pth
    wget -q -nc https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth -O ./gfpgan/weights/detection_Resnet50_Final.pth
    wget -q -nc https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth -O ./gfpgan/weights/GFPGANv1.4.pth
    wget -q -nc https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth -O ./gfpgan/weights/parsing_parsenet.pth
    set -e
    cd "$PROJECT_DIR" || exit 1
    echo "✅ SadTalker checkpoint'leri indirildi"
else
    echo "✅ SadTalker checkpoint'leri zaten mevcut"
fi

# GFPGAN ve RealESRGAN ağırlıkları (her zaman kontrol et)
cd "$SADTALKER_DIR"
mkdir -p ./checkpoints ./gfpgan/weights
if [ ! -f "./gfpgan/weights/GFPGANv1.4.pth" ]; then
    echo "  → GFPGANv1.4.pth indiriliyor..."
    wget -q -nc https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth -O ./gfpgan/weights/GFPGANv1.4.pth
fi
if [ ! -f "./checkpoints/RealESRGAN_x4plus.pth" ]; then
    echo "  → RealESRGAN_x4plus.pth indiriliyor..."
    wget -q -nc https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth -O ./checkpoints/RealESRGAN_x4plus.pth
fi
cd "$PROJECT_DIR" || exit 1

export SADTALKER_PATH="$SADTALKER_DIR"
export SADTALKER_CHECKPOINT_PATH="$SADTALKER_CHECKPOINTS"
echo "  → SADTALKER_PATH=$SADTALKER_PATH"
echo "  → SADTALKER_CHECKPOINT_PATH=$SADTALKER_CHECKPOINT_PATH"

# SadTalker np.float patch (bozuk np.float6464... dosyasını düzeltir)
AWING_ARCH="$SADTALKER_DIR/src/face3d/util/my_awing_arch.py"
if [ -f "$AWING_ARCH" ]; then
    python3 -c "
import re
with open('$AWING_ARCH','r') as f: c=f.read()
n=re.sub(r'np\.float64(64)+','np.float64',c)
n=re.sub(r'np\.float(?!\d)','np.float64',n)
if n!=c: open('$AWING_ARCH','w').write(n); print('Patched my_awing_arch.py')
" 2>/dev/null || true
fi

# 5. Gerekli klasörleri oluştur
echo ""
echo "📁 Klasörler oluşturuluyor..."
mkdir -p /workspace/datasets
mkdir -p /workspace/lora_storage
mkdir -p /workspace/audio
mkdir -p /workspace/video_raw
mkdir -p /workspace/video_final
echo "✅ Klasörler hazır"

# 5a. Python cache temizleme (Pydantic Settings güncellemeleri için)
echo ""
echo "🧹 Python cache temizleniyor..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cache temizlendi"

# 5b. Redis kurulumu ve başlatma (Celery için zorunlu)
echo ""
echo "🔴 Redis kontrol ediliyor..."
if ! command -v redis-server &> /dev/null; then
    echo "  → Redis kuruluyor..."
    if command -v apt-get &> /dev/null; then
        apt-get update -qq && apt-get install -y redis-server
        echo "✅ Redis kuruldu"
    else
        echo "❌ Redis kurulamadı (apt-get yok). Celery çalışmayacak!"
        echo "💡 Alternatif: .env'de REDIS_URL ile Upstash kullanın"
    fi
else
    echo "✅ Redis zaten kurulu"
fi
if command -v redis-server &> /dev/null; then
    # Redis çalışıyorsa yeniden başlatma
    if ! redis-cli ping &>/dev/null; then
        redis-server --daemonize yes
        sleep 1
    fi
    if redis-cli ping &>/dev/null; then
        echo "✅ Redis çalışıyor"
    else
        echo "⚠️  Redis başlatılamadı. Celery hata verebilir."
        echo "💡 Manuel: redis-server --daemonize yes"
    fi
fi

# 6. Veritabanını başlat
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

# 7. Ngrok token kontrolü (opsiyonel - environment variable'dan)
if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo ""
    echo "⚠️  NGROK_AUTHTOKEN environment variable bulunamadı"
    echo "💡 Ngrok'u token olmadan başlatıyoruz (ücretsiz plan)"
else
    ngrok config add-authtoken "$NGROK_AUTHTOKEN"
    echo "✅ Ngrok token ayarlandı"
fi

# 8. Eski process'leri temizle
echo ""
echo "🧹 Eski process'ler temizleniyor..."
pkill -f uvicorn || true
pkill -f ngrok || true
sleep 2

# 9. API'yi başlat (arka planda)
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

# 10. Ngrok'u başlat (arka planda)
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

# 11. (Opsiyonel) Celery Worker başlat — ön planda, loglar terminalde görünür
if [ "$START_CELERY_WORKER" = "true" ]; then
    echo ""
    echo "⚙️  Celery Worker başlatılıyor (loglar burada görünecek)..."
    echo "   API arka planda: tail -f /workspace/api.log"
    echo "   Ngrok arka planda: tail -f /workspace/ngrok.log"
    echo ""
    celery -A app.queue.celery_app worker --loglevel=info --queues=gpu,default
else
    echo ""
    echo "✅ Startup script tamamlandı!"
    echo "   Celery Worker başlatmak için: START_CELERY_WORKER=true ./start.sh"
fi
