/**
 * ACAD Assistant - Frontend Client Application.
 * Coordinates all 5 Core PRD Features:
 * 1. Dashboard & Monitoring (Charts, KPIs, Early Alert)
 * 2. Scan KTM Attendance (Webcam HUD, EasyOCR, ZXing Barcode, Audio Cues)
 * 3. AutoQuiz & Data Mining (Difficulty P, Discrimination D, K-Means Clustering)
 * 4. Accessibility Scan TTS (Doc OCR, Web Speech API with speed adjustment)
 * 5. Chat AI Bot (RAG via Gemini, Local Class Context)
 */

// Global State
let currentTab = "dashboard";
let activeMeetingId = 5;
let attendanceChartInstance = null;
let quizMasteryChartInstance = null;
let webcamStream = null;
let scanInterval = null;
let isScanning = false;
let allStudentsList = [];
let audioCtx = null;
let ttsUtterance = null;
let currentTtsSpeed = 1.0;
let chatHistory = [];
let latestGeneratedQuestions = [];

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
  loadAttendanceTable();
  loadQuizzesList();
  loadAllStudents();
  lucide.createIcons();
});

// ==========================================
// 1. TAB SWITCHING & ROUTING
// ==========================================
function switchTab(tabId) {
  currentTab = tabId;

  // Update nav buttons
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.className = "tab-btn flex items-center space-x-2 px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition";
  });
  const activeBtn = document.getElementById(`tab-${tabId}`);
  if (activeBtn) {
    activeBtn.className = "tab-btn flex items-center space-x-2 px-3 py-2 rounded-lg text-emerald-400 bg-emerald-500/10 border border-emerald-500/30";
  }

  // Hide all sections, show active
  document.querySelectorAll(".tab-content").forEach((sec) => {
    sec.classList.add("hidden");
  });
  const activeSec = document.getElementById(`view-${tabId}`);
  if (activeSec) {
    activeSec.classList.remove("hidden");
  }

  // Refresh tab-specific views
  if (tabId === "dashboard") {
    initDashboard();
  } else if (tabId === "attendance") {
    loadAttendanceTable();
  } else if (tabId === "autoquiz") {
    loadQuizzesList();
  } else if (tabId === "students") {
    loadAllStudents();
  }

  lucide.createIcons();
}

async function changeActiveMeeting(meetingId) {
  activeMeetingId = parseInt(meetingId);
  try {
    await fetch(`/api/meetings/${activeMeetingId}/set-active`, { method: "POST" });
    initDashboard();
    loadAttendanceTable();
  } catch (err) {
    console.error("Gagal mengganti sesi aktif:", err);
  }
}

// ==========================================
// 2. DASHBOARD & MONITORING (FITUR 1)
// ==========================================
async function initDashboard() {
  try {
    const res = await fetch("/api/dashboard");
    const json = await res.json();
    if (!json.success) return;
    const data = json.data;

    // 1. Update KPI Cards
    const kpi = data.kpi || {};
    document.getElementById("kpi-attendance-rate").textContent = `${kpi.weekly_attendance_rate}%`;
    document.getElementById("kpi-attendance-count").textContent = `(${kpi.hadir_count}/${kpi.total_students} Mhs)`;
    document.getElementById("kpi-active-meeting").textContent = `P${kpi.active_meeting_no}`;
    document.getElementById("kpi-quizzes-count").textContent = kpi.active_quiz_count;
    document.getElementById("kpi-need-review").textContent = kpi.need_review_topics_count;
    document.getElementById("kpi-at-risk").textContent = kpi.at_risk_students_count;

    // 2. Early Alert Banner
    const alertBox = document.getElementById("earlyAlertBanner");
    const alertText = document.getElementById("earlyAlertText");
    if (data.early_alert && data.early_alert.triggered) {
      alertBox.classList.remove("hidden");
      alertText.textContent = data.early_alert.message;
    } else {
      alertBox.classList.add("hidden");
    }

    // 3. Render Attendance Trend Chart
    renderAttendanceChart(data.attendance_trend || []);

    // 4. Render Quiz Mastery Chart
    renderQuizMasteryChart(data.quiz_performance || []);

    // 5. Render Critical Subtopics Table
    renderCriticalSubtopics(data.critical_subtopics || []);

  } catch (err) {
    console.error("Error loading dashboard:", err);
  }
}

function renderAttendanceChart(trends) {
  const ctx = document.getElementById("attendanceTrendChart");
  if (!ctx) return;

  const labels = trends.map((t) => `P${t.meeting_no}`);
  const dataPoints = trends.map((t) => t.rate);

  if (attendanceChartInstance) {
    attendanceChartInstance.destroy();
  }

  attendanceChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Persentase Kehadiran (%)",
          data: dataPoints,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34, 197, 94, 0.15)",
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointBackgroundColor: "#22c55e",
          pointRadius: 4.5,
          pointHoverRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Kehadiran: ${ctx.parsed.y}%`
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.06)" },
          ticks: { color: "#94a3b8", callback: (val) => `${val}%` }
        },
        x: {
          grid: { color: "rgba(255, 255, 255, 0.06)" },
          ticks: { color: "#94a3b8" }
        }
      }
    }
  });
}

function renderQuizMasteryChart(quizPerf) {
  const ctx = document.getElementById("quizMasteryChart");
  if (!ctx) return;

  const labels = quizPerf.map((q) => `Kuis P${q.meeting_no}`);
  const scores = quizPerf.map((q) => q.class_average);
  const bgColors = scores.map((s) => s < 50.0 ? "rgba(244, 63, 94, 0.75)" : "rgba(99, 102, 241, 0.75)");

  if (quizMasteryChartInstance) {
    quizMasteryChartInstance.destroy();
  }

  quizMasteryChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Rerata Skor Kuis",
          data: scores,
          backgroundColor: bgColors,
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Rata-rata: ${ctx.parsed.y}%`
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: "rgba(255, 255, 255, 0.06)" },
          ticks: { color: "#94a3b8", callback: (val) => `${val}%` }
        },
        x: {
          grid: { display: false },
          ticks: { color: "#94a3b8" }
        }
      }
    }
  });
}

function renderCriticalSubtopics(critList) {
  const tbody = document.getElementById("criticalSubtopicsTableBody");
  if (!tbody) return;

  if (critList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-slate-500 italic">Tidak ada sub-topik berstatus kritis pada kuis aktif.</td></tr>`;
    return;
  }

  tbody.innerHTML = critList.map((c) => `
    <tr class="hover:bg-slate-800/40 transition">
      <td class="py-2.5 px-3 font-medium text-white">${c.subtopic}</td>
      <td class="py-2.5 px-3 font-mono font-bold text-amber-400">${c.difficulty_p}</td>
      <td class="py-2.5 px-3 font-mono ${c.discrimination_d >= 0.3 ? "text-emerald-400" : "text-slate-400"}">${c.discrimination_d}</td>
      <td class="py-2.5 px-3">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
          Kritis (Need Review)
        </span>
      </td>
      <td class="py-2.5 px-3 text-slate-300">Sediakan penjelasan ulang 10 menit & remedial</td>
    </tr>
  `).join("");
}

// ==========================================
// 3. FITUR SCAN KTM – PRESENSI (FITUR 5)
// ==========================================
async function toggleWebcam() {
  const video = document.getElementById("webcamVideo");
  const placeholder = document.getElementById("cameraPlaceholder");
  const hudOverlay = document.getElementById("scannerHudOverlay");
  const btn = document.getElementById("cameraBtnText");

  if (webcamStream) {
    // Stop camera
    webcamStream.getTracks().forEach((track) => track.stop());
    webcamStream = null;
    video.classList.add("hidden");
    hudOverlay.classList.add("hidden");
    placeholder.classList.remove("hidden");
    btn.textContent = "Aktifkan Kamera";
    clearInterval(scanInterval);
    scanInterval = null;
    return;
  }

  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" }
    });
    video.srcObject = webcamStream;
    video.classList.remove("hidden");
    hudOverlay.classList.remove("hidden");
    placeholder.classList.add("hidden");
    btn.textContent = "Matikan Kamera";

    // Start auto scanning loop every 2.5s
    scanInterval = setInterval(() => {
      if (!isScanning) {
        captureCurrentFrame(true);
      }
    }, 2500);

  } catch (err) {
    alert("Tidak dapat mengakses kamera: " + err.message + "\nAnda dapat menggunakan tombol 'Uji Sampel Foto' atau 'Unggah Foto KTM'.");
  }
}

async function captureCurrentFrame(isAuto = false) {
  const video = document.getElementById("webcamVideo");
  if (!webcamStream || video.paused || video.ended) {
    if (!isAuto) alert("Silakan aktifkan kamera terlebih dahulu.");
    return;
  }

  const vw = video.videoWidth || 640;
  const vh = video.videoHeight || 480;

  // Crop center card ROI matching the green guide brackets (approx center 78% width, 68% height)
  const cropW = Math.floor(vw * 0.78);
  const cropH = Math.floor(vh * 0.68);
  const cropX = Math.floor((vw - cropW) / 2);
  const cropY = Math.floor((vh - cropH) / 2);

  const canvas = document.getElementById("captureCanvas");
  // Normalize target width to 640 max for fastest CPU inference (<1.5s)
  const targetW = 640;
  const targetH = Math.floor(cropH * (targetW / cropW));
  canvas.width = targetW;
  canvas.height = targetH;

  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, targetW, targetH);
  const base64Data = canvas.toDataURL("image/jpeg", 0.82);

  processScanPayload({ frame_base64: base64Data, meeting_id: activeMeetingId });
}

let currentScannedStudentNim = null;

async function resetStudentByNim(nim, name = "Mahasiswa") {
  if (!nim) return;
  try {
    const res = await fetch("/api/attendance/reset-student", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ meeting_id: activeMeetingId, student_nim: nim })
    });
    const json = await res.json();

    // Reset alert card back to standby if this student was the active card
    const card = document.getElementById("attendanceAlertCard");
    card.className = "bg-slate-900/90 border border-slate-700 rounded-xl p-5 text-center min-h-[220px] flex flex-col items-center justify-center transition-all duration-300";
    document.getElementById("alertHeadline").textContent = `Presensi ${name} Siap Diuji Ulang`;
    document.getElementById("alertHeadline").className = "text-base font-bold text-amber-300";
    document.getElementById("alertSubtext").textContent = `Status ${name} (${nim}) telah diubah menjadi 'Belum Hadir'. Silakan arahkan KTM fisik ke kamera untuk uji coba scan!`;
    document.getElementById("alertStudentDetails").classList.add("hidden");
    document.getElementById("scanStatusBadge").textContent = "Siap Pindai";
    document.getElementById("scanStatusBadge").className = "text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full font-medium border border-emerald-500/30";

    loadAttendanceTable();
    initDashboard();
  } catch (err) {
    alert("Gagal reset presensi mahasiswa: " + err.message);
  }
}

async function resetSelectedStudent() {
  const selector = document.getElementById("resetStudentSelector");
  const nim = selector.value;
  const name = selector.options[selector.selectedIndex]?.text?.split("(")[0]?.trim() || "Mahasiswa";
  resetStudentByNim(nim, name);
}

async function resetCurrentlyScannedStudent() {
  if (!currentScannedStudentNim) {
    alert("Belum ada mahasiswa yang dipindai saat ini.");
    return;
  }
  const name = document.getElementById("resStudentName")?.textContent || "Mahasiswa";
  resetStudentByNim(currentScannedStudentNim, name);
}

async function resetAllAttendance() {
  if (!confirm("Reset status kehadiran SELURUH 32 mahasiswa sesi ini ke 'Belum Hadir'?")) return;
  try {
    await fetch(`/api/attendance/reset-meeting?meeting_id=${activeMeetingId}`, { method: "POST" });
    
    // Reset alert card
    const card = document.getElementById("attendanceAlertCard");
    card.className = "bg-slate-900/90 border border-slate-700 rounded-xl p-5 text-center min-h-[220px] flex flex-col items-center justify-center transition-all duration-300";
    document.getElementById("alertHeadline").textContent = "Semua Mahasiswa Siap Diuji Ulang";
    document.getElementById("alertHeadline").className = "text-base font-bold text-emerald-300";
    document.getElementById("alertSubtext").textContent = "Seluruh 32 mahasiswa kini berstatus 'Belum Hadir'. Silakan pindai KTM kartu mana pun!";
    document.getElementById("alertStudentDetails").classList.add("hidden");

    loadAttendanceTable();
    initDashboard();
    alert("✓ Seluruh 32 mahasiswa sesi ini berhasil direset ke 'Belum Hadir'.");
  } catch (err) {
    alert("Gagal reset: " + err.message);
  }
}

async function testSampleCard(sampleFilename) {
  const card = document.getElementById("attendanceAlertCard");
  document.getElementById("alertHeadline").textContent = "Memindai Sampel KTM...";
  document.getElementById("alertSubtext").textContent = "Sedang mengekstrak teks EasyOCR dan mencocokkan basis data 07TPLP003...";
  
  try {
    const res = await fetch(`/api/attendance/sample-scan/${sampleFilename}?meeting_id=${activeMeetingId}`);
    const json = await res.json();
    handleScanResult(json.result);
  } catch (err) {
    console.error("Error sample scan:", err);
  }
}

async function uploadCardImage(input) {
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("meeting_id", activeMeetingId);

  document.getElementById("alertHeadline").textContent = "Memindai Foto Diunggah...";
  try {
    const res = await fetch("/api/attendance/upload-image", { method: "POST", body: formData });
    const json = await res.json();
    handleScanResult(json.result);
  } catch (err) {
    console.error("Error upload card:", err);
  }
}

async function processScanPayload(payload) {
  isScanning = true;
  const badge = document.getElementById("scanStatusBadge");
  badge.textContent = "Scanning...";
  badge.className = "text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-medium border border-amber-500/30";

  try {
    const res = await fetch("/api/attendance/scan-frame", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    handleScanResult(json.result);
  } catch (err) {
    console.error("Scan error:", err);
  } finally {
    isScanning = false;
  }
}

function handleScanResult(res) {
  if (!res) return;

  const card = document.getElementById("attendanceAlertCard");
  const iconBox = document.getElementById("alertIconBox");
  const headline = document.getElementById("alertHeadline");
  const subtext = document.getElementById("alertSubtext");
  const details = document.getElementById("alertStudentDetails");
  const badge = document.getElementById("scanStatusBadge");
  const ocrLatency = document.getElementById("ocrLatency");
  const rawTokens = document.getElementById("rawOcrTokens");

  ocrLatency.textContent = `Latency: ${res.elapsed_ms || "--"} ms`;

  // Render raw tokens preview
  if (res.raw_texts && res.raw_texts.length > 0) {
    rawTokens.innerHTML = res.raw_texts.map((t) => `<span class="bg-slate-800 text-emerald-300 px-1.5 py-0.5 rounded border border-slate-700">${t}</span>`).join(" ");
  } else {
    rawTokens.innerHTML = `<span class="text-slate-500 italic text-[11px]">Teks tidak terdeteksi pada frame</span>`;
  }

  if (res.detected && res.student) {
    const st = res.student;
    currentScannedStudentNim = st.nim;
    details.classList.remove("hidden");
    document.getElementById("resStudentName").textContent = st.name;
    document.getElementById("resStudentNim").textContent = st.nim;
    document.getElementById("resTimestamp").textContent = st.timestamp;
    document.getElementById("resMethod").textContent = `${st.method} (${st.confidence}%)`;

    const btnResetCardText = document.getElementById("btnResetScannedText");
    if (btnResetCardText) {
      btnResetCardText.textContent = `Reset ${st.name} (Uji Scan Ulang)`;
    }

    if (res.already_attended) {
      // Amber/Blue Alert: Sudah Melakukan Presensi
      card.className = "bg-amber-950/40 border-2 border-amber-500 rounded-xl p-5 text-center min-h-[220px] flex flex-col items-center justify-center transition shadow-[0_0_25px_rgba(245,158,11,0.2)]";
      iconBox.className = "w-14 h-14 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center mb-3";
      iconBox.innerHTML = `<i data-lucide="info" class="w-7 h-7"></i>`;
      headline.textContent = "SUDAH MELAKUKAN PRESENSI";
      headline.className = "text-base font-bold text-amber-400";
      subtext.textContent = `Mahasiswa ${st.name} telah tercatat hadir pada pukul ${st.timestamp}.`;
      badge.textContent = "Duplikasi Ditolak";
      badge.className = "text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-medium border border-amber-500/30";

      playBeep(800); // 800Hz warning beep
      speakVoice(`Mahasiswa ${st.name} sudah melakukan presensi sebelumnya.`);
    } else {
      // Green Alert: Presensi Berhasil
      card.className = "bg-emerald-950/40 border-2 border-emerald-500 rounded-xl p-5 text-center min-h-[220px] flex flex-col items-center justify-center transition shadow-[0_0_30px_rgba(34,197,94,0.3)]";
      iconBox.className = "w-14 h-14 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mb-3";
      iconBox.innerHTML = `<i data-lucide="check-circle" class="w-7 h-7"></i>`;
      headline.textContent = "PRESENSI BERHASIL!";
      headline.className = "text-base font-bold text-emerald-400";
      subtext.textContent = `Kehadiran mahasiswa berhasil diverifikasi dan dicatat ke database.`;
      badge.textContent = "Terverifikasi";
      badge.className = "text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full font-medium border border-emerald-500/30";

      playBeep(1400); // 1400Hz success chime
      speakVoice(`Presensi tercatat: ${st.name}`);

      // Refresh live table and dashboard
      loadAttendanceTable();
      initDashboard();
    }
  } else {
    // Red Alert: Tidak Dikenali
    details.classList.add("hidden");
    card.className = "bg-rose-950/30 border-2 border-rose-500/80 rounded-xl p-5 text-center min-h-[220px] flex flex-col items-center justify-center transition";
    iconBox.className = "w-14 h-14 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center mb-3";
    iconBox.innerHTML = `<i data-lucide="x-circle" class="w-7 h-7"></i>`;
    headline.textContent = "KARTU TIDAK DIKENALI";
    headline.className = "text-base font-bold text-rose-400";
    subtext.textContent = "Pastikan KTM berada tepat di tengah kotak panduan dan tidak tertutup jari.";
    badge.textContent = "Gagal Verifikasi";
    badge.className = "text-xs bg-rose-500/20 text-rose-300 px-2 py-0.5 rounded-full font-medium border border-rose-500/30";
  }

  lucide.createIcons();
}

async function loadAttendanceTable() {
  try {
    const res = await fetch(`/api/attendance?meeting_id=${activeMeetingId}`);
    const json = await res.json();
    if (!json.success) return;

    const badge = document.getElementById("attendanceSummaryBadge");
    badge.textContent = `Hadir: ${json.hadir_count} / ${json.total_count}`;

    // Populate universal resetStudentSelector dropdown if empty or on reload
    const resetSel = document.getElementById("resetStudentSelector");
    if (resetSel && json.attendance) {
      const currentVal = resetSel.value;
      resetSel.innerHTML = json.attendance.map((st) => `
        <option value="${st.nim}">${st.name} (${st.nim.slice(-4)})</option>
      `).join("");
      if (currentVal && Array.from(resetSel.options).some(o => o.value === currentVal)) {
        resetSel.value = currentVal;
      }
    }

    const tbody = document.getElementById("attendanceTableBody");
    tbody.innerHTML = json.attendance.map((row, idx) => {
      const isHadir = row.status === "Hadir";
      return `
        <tr class="hover:bg-slate-800/50 transition">
          <td class="py-2.5 px-3 font-mono text-slate-500 text-[11px]">${idx + 1}</td>
          <td class="py-2.5 px-3 font-mono font-bold text-emerald-400">${row.nim}</td>
          <td class="py-2.5 px-3 font-medium text-white">${row.name}</td>
          <td class="py-2.5 px-3">
            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
              isHadir
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                : "bg-slate-700/60 text-slate-400"
            }">
              ${row.status}
            </span>
          </td>
          <td class="py-2.5 px-3 font-mono text-slate-300">${row.timestamp || "-"}</td>
          <td class="py-2.5 px-3 text-slate-400">${row.method || "-"}</td>
          <td class="py-2.5 px-3 text-right">
            ${
              isHadir
                ? `<button onclick="resetStudentByNim('${row.nim}', '${row.name}')" class="text-[11px] text-amber-400 hover:text-amber-300 font-semibold hover:underline flex items-center space-x-1 ml-auto">
                    <span>🔄 Reset Belum Hadir</span>
                   </button>`
                : `<button onclick="toggleAttendanceManual('${row.nim}', 'Hadir')" class="text-[11px] text-emerald-400 hover:text-emerald-300 hover:underline font-semibold flex items-center space-x-1 ml-auto">
                    <span>✓ Tandai Hadir</span>
                   </button>`
            }
          </td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading attendance table:", err);
  }
}

async function toggleAttendanceManual(nim, newStatus) {
  try {
    await fetch("/api/attendance/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ meeting_id: activeMeetingId, student_nim: nim, status: newStatus })
    });
    loadAttendanceTable();
    initDashboard();
  } catch (err) {
    console.error("Error toggle attendance:", err);
  }
}

// ==========================================
// AUDIO SYNTHESIS & BEEP HELPER
// ==========================================
function playBeep(freq = 1400, duration = 0.15) {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!audioCtx) audioCtx = new AudioContext();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch (e) {
    console.warn("Web Audio tidak didukung atau diblokir browser");
  }
}

function speakVoice(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "id-ID";
  utter.rate = 1.05;
  window.speechSynthesis.speak(utter);
}

// ==========================================
// 4. AUTOQUIZ & DATA MINING (FITUR 3)
// ==========================================
async function generateAutoQuiz() {
  const topic = document.getElementById("quizTopicInput").value.trim();
  const material = document.getElementById("quizMaterialInput").value.trim();
  const count = parseInt(document.getElementById("quizCountSelect").value);
  const btn = document.getElementById("btnGenerateQuiz");

  if (!topic) {
    alert("Silakan masukkan topik perkuliahan terlebih dahulu.");
    return;
  }

  btn.innerHTML = `<span class="animate-spin mr-1">⌛</span> Menghasilkan Soal via Gemini AI...`;
  btn.disabled = true;

  try {
    const res = await fetch("/api/quizzes/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, material_text: material, count, meeting_id: activeMeetingId })
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.detail || "Gagal menghasilkan soal");

    latestGeneratedQuestions = json.questions;
    renderQuizPreview(latestGeneratedQuestions);
  } catch (err) {
    alert("Terjadi kesalahan: " + err.message);
  } finally {
    btn.innerHTML = `<i data-lucide="sparkles" class="w-4 h-4"></i><span>Buat Quick Quiz Pertemuan Ini</span>`;
    btn.disabled = false;
    lucide.createIcons();
  }
}

async function handleQuizPdfUpload(input) {
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("meeting_id", activeMeetingId);
  formData.append("count", parseInt(document.getElementById("quizCountSelect")?.value || "3"));

  const btn = document.getElementById("btnUploadPdfQuiz");
  const btnText = document.getElementById("btnUploadPdfQuizText");
  const statusText = document.getElementById("pdfUploadStatusText");

  btn.disabled = true;
  btnText.textContent = "Mengekstrak PDF & Membuat Soal...";
  statusText.classList.remove("hidden");
  statusText.textContent = `Memproses dokumen "${file.name}" via Gemini AI...`;

  try {
    const res = await fetch("/api/quizzes/generate-from-pdf", {
      method: "POST",
      body: formData
    });
    const json = await res.json();
    if (!json.success) throw new Error(json.detail || "Gagal membuat kuis dari PDF");

    latestGeneratedQuestions = json.questions;
    renderQuizPreview(latestGeneratedQuestions);

    document.getElementById("quizTopicInput").value = json.topic || file.name;
    statusText.textContent = `✓ Sukses membuat ${latestGeneratedQuestions.length} butir soal dari "${file.name}" (${json.word_count || 0} kata)!`;

    // Scroll to preview container
    document.getElementById("quizPreviewContainer").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("Terjadi kesalahan saat memproses file PDF: " + err.message);
    statusText.textContent = "Gagal memproses file PDF.";
  } finally {
    btn.disabled = false;
    btnText.textContent = "Unggah PDF Materi Kuliah";
    input.value = "";
    lucide.createIcons();
  }
}

function renderQuizPreview(questions) {
  const container = document.getElementById("quizPreviewContainer");
  const list = document.getElementById("questionsPreviewList");
  container.classList.remove("hidden");

  list.innerHTML = questions.map((q, idx) => `
    <div class="bg-slate-900 border border-slate-700/80 rounded-xl p-4 text-xs space-y-2">
      <div class="flex items-start justify-between">
        <span class="font-bold text-white">Butir ${idx + 1}: ${q.question}</span>
        <span class="bg-indigo-500/20 text-indigo-300 font-semibold px-2 py-0.5 rounded text-[10px] border border-indigo-500/30">
          Subtopik: ${q.subtopic}
        </span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-1.5 pt-1">
        ${q.options.map((opt) => `
          <div class="p-2 rounded bg-slate-800/70 border border-slate-700/60 ${opt.startsWith(q.correct) ? "border-emerald-500/80 bg-emerald-950/20 text-emerald-300 font-semibold" : "text-slate-300"}">
            ${opt}
          </div>
        `).join("")}
      </div>
      <p class="text-[11px] text-slate-400 italic pt-1">💡 Pembahasan: ${q.explanation}</p>
    </div>
  `).join("");
}

async function approveAndPublishQuiz() {
  if (latestGeneratedQuestions.length === 0) return;
  const topic = document.getElementById("quizTopicInput").value.trim();

  try {
    const res = await fetch("/api/quizzes/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        meeting_id: activeMeetingId,
        title: `Quick Quiz Pertemuan ${activeMeetingId}`,
        topic: topic,
        questions: latestGeneratedQuestions
      })
    });
    const json = await res.json();
    alert(`✓ Kuis berhasil disetujui dan diterbitkan untuk Pertemuan ${activeMeetingId}!`);
    document.getElementById("quizPreviewContainer").classList.add("hidden");
    loadQuizzesList();
    initDashboard();
  } catch (err) {
    alert("Gagal menyimpan kuis: " + err.message);
  }
}

async function loadQuizzesList() {
  try {
    const res = await fetch("/api/quizzes");
    const json = await res.json();
    if (!json.success) return;

    const selector = document.getElementById("activeQuizSelector");
    selector.innerHTML = json.quizzes.map((q) => `
      <option value="${q.id}">Kuis P${q.meeting_no}: ${q.title} (${q.submission_count} Jawaban)</option>
    `).join("");

    if (json.quizzes.length > 0) {
      loadQuizAnalytics(json.quizzes[0].id);
    }
  } catch (err) {
    console.error("Error load quizzes:", err);
  }
}

async function loadQuizAnalytics(quizId) {
  try {
    const res = await fetch(`/api/quizzes/${quizId}`);
    const json = await res.json();
    if (!json.success) return;

    const an = json.analytics;
    document.getElementById("quizClassAvgBadge").textContent = `Rerata Nilai: ${an.class_average}% (${an.total_respondents} Mahasiswa)`;

    const tbody = document.getElementById("psychometricsTableBody");
    tbody.innerHTML = (an.items || []).map((it, idx) => `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="py-2.5 px-3 font-mono text-slate-400">${idx + 1}</td>
        <td class="py-2.5 px-3 font-medium text-white">${it.subtopic}</td>
        <td class="py-2.5 px-3 font-mono font-bold ${it.difficulty_p < 0.4 ? "text-rose-400" : "text-emerald-400"}">
          ${it.difficulty_p} (${it.difficulty_label})
        </td>
        <td class="py-2.5 px-3 font-mono ${it.discrimination_d >= 0.3 ? "text-emerald-400 font-bold" : "text-slate-400"}">
          ${it.discrimination_d} (${it.discrimination_label})
        </td>
        <td class="py-2.5 px-3">
          ${
            it.is_critical
              ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">Kritis (Review)</span>`
              : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Tercapai</span>`
          }
        </td>
      </tr>
    `).join("");

    // Load Cluster Counts
    loadClusterBadges();

  } catch (err) {
    console.error("Error quiz analytics:", err);
  }
}

async function simulateClassQuiz() {
  const quizId = document.getElementById("activeQuizSelector").value;
  if (!quizId) return;

  try {
    const res = await fetch(`/api/quizzes/${quizId}/simulate-class?pass_rate=0.72`, { method: "POST" });
    const json = await res.json();
    alert("⚡ Sukses! 32 respons mahasiswa kelas 07TPLP003 telah disimulasikan.");
    loadQuizAnalytics(quizId);
    initDashboard();
  } catch (err) {
    alert("Gagal mensimulasikan kuis: " + err.message);
  }
}

async function loadClusterBadges() {
  try {
    const res = await fetch("/api/students");
    const json = await res.json();
    if (!json.success) return;
    const counts = json.data.counts || {};
    document.getElementById("clusterMasteredCount").textContent = `${counts.mastered || 0} Mhs`;
    document.getElementById("clusterBorderlineCount").textContent = `${counts.borderline || 0} Mhs`;
    document.getElementById("clusterAtRiskCount").textContent = `${counts.at_risk || 0} Mhs`;
  } catch (e) {}
}

// ==========================================
// 5. FITUR AKSESIBILITAS (SCAN TEXT TO SPEECH)
// ==========================================
async function handleDocFileUpload(input) {
  if (!input.files || input.files.length === 0) return;
  const file = input.files[0];
  const formData = new FormData();
  formData.append("file", file);

  const textarea = document.getElementById("docExtractedTextArea");
  textarea.value = "Sedang mengekstrak teks dokumen via OCR Engine...";

  try {
    const res = await fetch("/api/accessibility/ocr", { method: "POST", body: formData });
    const json = await res.json();
    if (!json.success) throw new Error(json.data?.error || "Gagal OCR");

    textarea.value = json.data.text;
    document.getElementById("docWordCount").textContent = `${json.data.word_count} Kata`;
  } catch (err) {
    textarea.value = "Error: " + err.message;
  }
}

function loadSampleText(type) {
  const textarea = document.getElementById("docExtractedTextArea");
  if (type === "eva") {
    textarea.value = `Earned Value Analysis (EVA) adalah metode standar industri untuk mengukur kinerja dan kemajuan proyek perangkat lunak secara objektif. 

Tiga metrik utama dalam EVA meliputi:
1. Planned Value (PV), yaitu nilai anggaran biaya pekerjaan yang dijadwalkan selesai pada periode tertentu.
2. Earned Value (EV), yaitu nilai pekerjaan yang secara aktual telah berhasil diselesaikan oleh tim proyek.
3. Actual Cost (AC), yaitu biaya nyata yang dikeluarkan untuk melaksanakan pekerjaan tersebut.

Berdasarkan metrik ini, manajer proyek dapat menghitung Schedule Variance (SV = EV - PV) dan Cost Variance (CV = EV - AC). Nilai CPI atau Cost Performance Index yang lebih kecil dari satu menunjukkan bahwa proyek sedang mengalami pembengkakan anggaran (Over Budget).`;
  } else {
    textarea.value = `Aturan 100% Rule dalam Work Breakdown Structure (WBS) menyatakan bahwa dekomposisi WBS harus mencakup 100% ruang lingkup pekerjaan yang didefinisikan oleh scope proyek dan menangkap semua deliverables, baik internal maupun eksternal.

Aturan ini berlaku pada setiap tingkat hierarki: jumlah pekerjaan pada tingkat "anak" harus sama dengan 100% pekerjaan yang diwakili oleh "induk". Tidak boleh ada aktivitas proyek di luar WBS, dan tidak boleh ada pekerjaan yang tercantum dua kali untuk mencegah duplikasi biaya dan tenaga.`;
  }
  document.getElementById("docWordCount").textContent = `${textarea.value.split(/\s+/).length} Kata`;
}

function playTTS() {
  const text = document.getElementById("docExtractedTextArea").value.trim();
  if (!text) {
    alert("Tidak ada teks untuk dibacakan.");
    return;
  }

  if (!("speechSynthesis" in window)) {
    alert("Browser tidak mendukung Web Speech API");
    return;
  }

  window.speechSynthesis.cancel();
  ttsUtterance = new SpeechSynthesisUtterance(text);
  ttsUtterance.lang = "id-ID";
  ttsUtterance.rate = currentTtsSpeed;

  ttsUtterance.onstart = () => {
    document.getElementById("ttsStatusIndicator").textContent = "Sedang memutar audio...";
    document.getElementById("ttsStatusIndicator").className = "text-[11px] text-emerald-400 font-semibold animate-pulse";
  };
  ttsUtterance.onend = () => {
    document.getElementById("ttsStatusIndicator").textContent = "Selesai dibacakan";
    document.getElementById("ttsStatusIndicator").className = "text-[11px] text-slate-400";
  };

  window.speechSynthesis.speak(ttsUtterance);
}

function pauseTTS() {
  if (window.speechSynthesis.speaking) {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      document.getElementById("ttsStatusIndicator").textContent = "Melanjutkan audio...";
    } else {
      window.speechSynthesis.pause();
      document.getElementById("ttsStatusIndicator").textContent = "Jeda (Paused)";
    }
  }
}

function stopTTS() {
  window.speechSynthesis.cancel();
  document.getElementById("ttsStatusIndicator").textContent = "Audio dihentikan";
}

function updateTtsSpeed(val) {
  currentTtsSpeed = parseFloat(val);
  document.getElementById("speedValueText").textContent = `${currentTtsSpeed}x`;
  if (window.speechSynthesis.speaking) {
    playTTS();
  }
}

function copyDocText() {
  const text = document.getElementById("docExtractedTextArea").value;
  navigator.clipboard.writeText(text);
  alert("Teks berhasil disalin!");
}

// ==========================================
// 6. CHAT AI BOT (RAG VIA GEMINI)
// ==========================================
async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const msg = input.value.trim();
  if (!msg) return;

  input.value = "";
  appendChatBubble("user", msg);

  const sendBtn = document.getElementById("btnSendChat");
  sendBtn.disabled = true;

  // Assistant typing bubble
  const typingId = "typing-" + Date.now();
  appendTypingIndicator(typingId);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, history: chatHistory })
    });
    const json = await res.json();
    removeTypingIndicator(typingId);

    if (json.success) {
      appendChatBubble("assistant", json.reply, json.speech_text);
      chatHistory.push({ role: "user", content: msg });
      chatHistory.push({ role: "assistant", content: json.reply });
    } else {
      appendChatBubble("assistant", "Maaf, terjadi kendala: " + json.detail);
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    appendChatBubble("assistant", "Koneksi terputus: " + err.message);
  } finally {
    sendBtn.disabled = false;
    lucide.createIcons();
  }
}

function sendQuickPrompt(promptText) {
  document.getElementById("chatInput").value = promptText;
  sendChatMessage();
}

function askChatbotTopicRemedial() {
  switchTab("chatbot");
  sendQuickPrompt("Rangkum materi WBS dan Critical Path yang sulit dipahami mahasiswa, dan buatkan panduan review 10 menit.");
}

function appendChatBubble(role, content, speechText = "") {
  const box = document.getElementById("chatMessagesBox");
  const div = document.createElement("div");
  const isUser = role === "user";

  div.className = isUser ? "flex items-start justify-end space-x-2" : "flex items-start space-x-3 max-w-2xl";

  const formattedHtml = content
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, "<code class='bg-slate-800 px-1 py-0.5 rounded text-emerald-400 font-mono'>$1</code>")
    .replace(/\n/g, "<br>");

  div.innerHTML = isUser
    ? `
      <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-2.5 max-w-md shadow-sm">
        ${formattedHtml}
      </div>
    `
    : `
      <div class="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 text-white shadow">
        <i data-lucide="bot" class="w-4 h-4"></i>
      </div>
      <div class="bg-slate-900 border border-slate-700/80 rounded-2xl rounded-tl-none p-4 text-slate-200 space-y-2 shadow-sm">
        <div>${formattedHtml}</div>
        <div class="pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
          <span>ACAD AI RAG</span>
          <button onclick="speakVoice('${encodeURIComponent(speechText || content)}')" class="hover:text-emerald-400 flex items-center space-x-1">
            <i data-lucide="volume-2" class="w-3.5 h-3.5"></i>
            <span>Dengarkan Suara</span>
          </button>
        </div>
      </div>
    `;

  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  lucide.createIcons();
}

function appendTypingIndicator(id) {
  const box = document.getElementById("chatMessagesBox");
  const div = document.createElement("div");
  div.id = id;
  div.className = "flex items-start space-x-3";
  div.innerHTML = `
    <div class="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 text-white">
      <i data-lucide="bot" class="w-4 h-4"></i>
    </div>
    <div class="bg-slate-900 border border-slate-700 rounded-2xl p-3 text-slate-400 flex items-center space-x-1 text-xs">
      <span>AI sedang menganalisis data kelas</span>
      <span class="animate-bounce">.</span><span class="animate-bounce delay-100">.</span><span class="animate-bounce delay-200">.</span>
    </div>
  `;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function clearChatHistory() {
  chatHistory = [];
  document.getElementById("chatMessagesBox").innerHTML = "";
  appendChatBubble("assistant", "Riwayat percakapan telah dibersihkan. Silakan ajukan pertanyaan baru!");
}

// ==========================================
// 7. DATA MAHASISWA 07TPLP003 (FITUR 6)
// ==========================================
async function loadAllStudents() {
  try {
    const res = await fetch("/api/students");
    const json = await res.json();
    if (!json.success) return;

    allStudentsList = json.data.students || [];
    renderStudentsTable(allStudentsList);
  } catch (err) {
    console.error("Error loading students list:", err);
  }
}

function renderStudentsTable(students) {
  const tbody = document.getElementById("allStudentsTableBody");
  tbody.innerHTML = students.map((st, idx) => {
    let clusterBadge = "";
    if (st.cluster === "Mastered") {
      clusterBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Mastered</span>`;
    } else if (st.cluster === "Borderline") {
      clusterBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">Borderline</span>`;
    } else {
      clusterBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 font-bold">At-Risk (Remedial)</span>`;
    }

    return `
      <tr class="hover:bg-slate-800/50 transition">
        <td class="py-2.5 px-3 font-mono text-slate-500 text-[11px]">${idx + 1}</td>
        <td class="py-2.5 px-3 font-mono font-bold text-emerald-400">${st.nim}</td>
        <td class="py-2.5 px-3 font-medium text-white">${st.name}</td>
        <td class="py-2.5 px-3 font-mono ${st.attendance_rate < 75 ? "text-rose-400 font-bold" : "text-slate-300"}">
          ${st.attendance_rate}% (${st.hadir_count}/${st.total_meetings} sesi)
        </td>
        <td class="py-2.5 px-3 font-mono font-bold ${st.quiz_avg < 60 ? "text-rose-400" : "text-emerald-400"}">
          ${st.quiz_avg}
        </td>
        <td class="py-2.5 px-3">${clusterBadge}</td>
      </tr>
    `;
  }).join("");
}

function filterStudentsTable(query) {
  const q = query.toLowerCase().trim();
  const filtered = allStudentsList.filter(
    (st) => st.name.toLowerCase().includes(q) || st.nim.includes(q)
  );
  renderStudentsTable(filtered);
}
