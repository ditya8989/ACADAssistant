# ACAD Assistant (Academic AI Assistant for Lecturers)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)
![EasyOCR](https://img.shields.io/badge/EasyOCR-CV%20Machine%20Learning-orange.svg)
![Gemini AI](https://img.shields.io/badge/Google%20Gemini-LLM%20RAG-8E75C4.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-Responsive%20SPA-38B2AC.svg)

> **ACAD Assistant** adalah asisten akademik cerdas berbasis Web & Computer Vision untuk dosen perguruan tinggi. Aplikasi ini mengotomatiskan presensi tatap muka melalui pemindaian KTM (Kartu Tanda Mahasiswa), menyediakan aksesibilitas materi ajar via OCR & Text-to-Speech (TTS), membuat kuis kilat otomatis dari dokumen PDF atau topik silabus, serta menganalisis daya serap kelas secara mendalam melalui teknik *Data Mining & Psikometrik* (Item Difficulty Index, Discrimination Index, Anomaly Detection, dan K-Means Student Risk Clustering).

---

## 🌟 5 Fitur Utama Sesuai PRD

### 1. 📊 Home Beranda (Grafik & Monitoring Kelas)
* **KPI Cards:** Ringkasan persentase kehadiran minggu berjalan, kuis aktif, sub-topik berstatus *"Perlu Review"*, dan jumlah mahasiswa berisiko (*At-Risk*).
* **Grafik Tren Kehadiran:** Line Chart interaktif perbandingan absensi antar pertemuan (Pertemuan 1 s.d. 8).
* **Heatmap / Bar Chart Pemahaman:** Visualisasi tingkat pemahaman kelas per pertemuan.
* **Early Alert Banner:** Banner peringatan otomatis berwarna merah menyala apabila rata-rata pemahaman pertemuan anjlok di bawah 50%.
* **Filter Akademik:** Filter dinamis berdasarkan Tahun Akademik, Semester, Program Studi, dan Mata Kuliah (default: *MPI-07TPLP003*).

### 2. 🎧 Fitur Aksesibilitas (Scan Text to Speech)
* Pemindaian materi ajar fisik (buku/catatan) atau dokumen digital via **OCR Multi-Bahasa** (Indonesia & Inggris).
* Dukungan unggah file gambar (`JPG`, `PNG`) dan dokumen dokumen (`PDF`).
* Editor teks hasil ekstraksi yang dapat dikoreksi langsung oleh dosen.
* Pemutar audio cerdas (*Text-to-Speech*) dengan aksen natural Bahasa Indonesia serta slider pengatur kecepatan baca (**0.75x hingga 2.0x**).

### 3. 🧠 AutoQuiz Pemahaman & Data Mining Detector
* **Generator Kuis Otomatis:** Dosen dapat membuat kuis kilat 3–5 soal pilihan ganda berdasarkan topik atau langsung **mengunggah file PDF modul perkuliahan**.
* **Integrasi AI / Fallback Pintar:** Didukung oleh Google Gemini (`gemini-2.5-flash` / `gemini-1.5-flash`) dengan fallback template deterministik jika offline.
* **Data Mining & Psychometrics Engine:**
  * **Item Difficulty Index ($P = B / N$):** Mengukur tingkat kesulitan soal. Soal bernilai $P < 0.4$ otomatis ditandai sebagai materi kritis yang belum dikuasai kelas.
  * **Discrimination Index ($D$):** Membedakan apakah kegagalan mahasiswa disebabkan materi belum tuntas atau butir soal yang ambigu.
  * **Anomaly Detection:** Mendeteksi penurunan performa ekstrem pada pertemuan tertentu dibanding rata-rata kelas.
  * **K-Means Student Risk Clustering:** Mengelompokkan mahasiswa ke dalam 3 segmen:
    * 🟢 **Mastered** (Paham penuh)
    * 🟡 **Borderline** (Perlu pendampingan)
    * 🔴 **At-Risk** (Prioritas remedial)

### 4. 🤖 Chat AI Bot (RAG Assistant)
* **Retrieval-Augmented Generation (RAG):** AI Assistant berkonsultasi langsung ke basis data lokal kelas 07TPLP003 secara real-time.
* **Conversational Query:** Dosen dapat menanyakan presensi bermasalah (*contoh: "Tampilkan mahasiswa yang kehadirannya di bawah 75%"*), evaluasi kuis, hingga rekomendasi bahan ajar remedial.
* **Fitur Text-to-Audio:** Jawaban chatbot dapat langsung didengarkan melalui tombol speaker audio.

### 5. 📷 Presensi Scan KTM (Computer Vision & Machine Learning)
* **Dual-Path Scanning Pipeline:**
  * **Fast-Path (<20ms):** Barcode / QR Code decoding via `zxing-cpp`.
  * **Deep Vision Path:** Anti-glare CLAHE preprocessing + EasyOCR neural recognition.
* **Fuzzy Name Matching:** Algoritma RapidFuzz dengan toleransi kemiripan $\ge 70\%$ untuk mengenali nama mahasiswa meskipun NIM pada kartu tergores atau terpotong.
* **Client-side ROI Cropping:** Webcam secara cerdas mencrop area kartu beresolusi 640px untuk kecepatan inferensi maksimal (~1.5 detik per kartu).
* **Universal Reset Pengujian:**
  * Tombol Reset per mahasiswa yang baru saja discan.
  * Dropdown Reset untuk memilih mahasiswa mana saja dari 32 mahasiswa kelas.
  * Tombol Reset Seluruh Kelas untuk memulai sesi pengujian baru.
* **Audio Feedback:** Bunyi beep frekuensi tinggi (1400Hz) saat presensi sukses tercatat, dan frekuensi rendah (800Hz) jika sudah pernah presensi.

---

## 📁 Struktur Repositori

```text
ACADAssistant/
├── .env.example              # Template variabel lingkungan (GEMINI_API_KEY)
├── .gitignore                # File yang dikecualikan dari Git tracking
├── README.md                 # Dokumentasi lengkap proyek
├── requirements.txt          # Daftar pustaka Python yang dibutuhkan
├── run.py                    # Script runner utama (Uvicorn FastAPI server)
├── run_app.bat               # Launcher satu-klik untuk Windows Explorer
└── backend/
    ├── app.py                # Server FastAPI & endpoint REST API
    ├── data/
    │   ├── mahasiswa.csv     # Data resmi 32 mahasiswa Kelas 07TPLP003
    │   └── samples/          # Contoh gambar kartu & dokumen uji coba
    ├── database/
    │   └── db_manager.py     # Thread-safe SQLite manager & auto-seeder
    ├── modules/
    │   ├── accessibility/
    │   │   └── doc_ocr.py    # Modul OCR Dokumen & Ekstraksi PDF
    │   ├── attendance/
    │   │   ├── barcode_engine.py # Fast barcode / QR scanner
    │   │   ├── matcher.py        # Dual-path matcher (NIM + RapidFuzz)
    │   │   ├── ocr_engine.py     # EasyOCR wrapper dengan eager warmup
    │   │   ├── preprocessor.py   # CLAHE anti-glare image enhancer
    │   │   └── scanner.py        # Unified scanner coordinator
    │   ├── chatbot/
    │   │   └── rag_engine.py     # RAG context injector & Gemini API caller
    │   └── data_mining/
    │       └── psychometrics.py  # Algoritma K-Means, P Index, D Index
    └── static/
        ├── app.js            # Frontend logic (SPA, WebRTC, Audio TTS, Chart.js)
        └── index.html        # UI dashboard modern berbasis Tailwind CSS
```

---

## 🚀 Panduan Instalasi & Menjalankan

### 1. Prasyarat Sistem
* Python 3.10 atau versi yang lebih baru (disarankan 3.10 – 3.12).
* Webcam / Kamera aktif (untuk fitur Scan Presensi KTM).
* Koneksi internet (untuk mengunduh bobot EasyOCR pertama kali dan akses Gemini AI).

### 2. Clone Repositori
```bash
git clone https://github.com/<username-anda>/ACADAssistant.git
cd ACADAssistant
```

### 3. Buat Virtual Environment & Install Dependensi
```bash
# Membuat virtual environment
python -m venv venv

# Mengaktifkan venv (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Mengaktifkan venv (Windows Command Prompt)
.\venv\Scripts\activate.bat

# Mengaktifkan venv (Linux / macOS)
source venv/bin/activate

# Menginstal dependensi
pip install -r requirements.txt
```

### 4. Konfigurasi API Key (Opsional untuk AI Penuh)
Buat file `.env` di folder utama atau set environment variable:
```powershell
# Windows PowerShell
$env:GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"

# Windows Command Prompt
set GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere

# Linux / macOS
export GEMINI_API_KEY="AIzaSyYourGeminiApiKeyHere"
```
*(Catatan: Jika API key tidak diisi, sistem tetap berfungsi normal menggunakan generator kuis lokal dan chatbot fallback)*.

### 5. Menjalankan Aplikasi
Cukup jalankan script:
```bash
python run.py
```
Atau di Windows, Anda dapat **klik dua kali** file `run_app.bat`.

Buka peramban (browser) di alamat:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 👥 Data Mahasiswa Kelas 07TPLP003

Aplikasi telah terkonfigurasi dengan data asli **32 Mahasiswa Kelas 07TPLP003** Universitas Pamulang di file `backend/data/mahasiswa.csv`, termasuk:
* `231011402760` — MUHAMMAD ADITYA
* Dan 31 mahasiswa lainnya lengkap dengan NIM dan nama sesuai absensi perkuliahan.

Database SQLite (`backend/data/acad_assistant.db`) akan diinisialisasi dan diisi otomatis (*auto-seed*) saat aplikasi dijalankan pertama kali.

---

## 📄 Lisensi
Dikembangkan untuk keperluan akademik dan penelitian peningkatan efisiensi pengajaran perguruan tinggi.
