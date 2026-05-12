const API = window.location.origin + "/api";

let state = {
  fileId: null,
  filename: "",
  totalPages: 1,
  currentPage: 1,
  ocrCache: {},
};

const $ = (sel) => document.querySelector(sel);
const uploadZone = $("#upload-zone");
const fileInput = $("#file-input");
const uploadProgress = $("#upload-progress");
const viewer = $("#viewer");
const filenameDisplay = $("#filename-display");
const pageImage = $("#page-image");
const currentPageEl = $("#current-page");
const totalPagesEl = $("#total-pages");
const btnPrev = $("#btn-prev");
const btnNext = $("#btn-next");
const btnOcrPage = $("#btn-ocr-page");
const btnOcrAll = $("#btn-ocr-all");
const btnCopy = $("#btn-copy");
const btnDownload = $("#btn-download");
const ocrContent = $("#ocr-content");
const ocrRaw = $("#ocr-raw");
const ocrRawSection = $("#ocr-raw-section");
const ocrRenderedSection = $("#ocr-rendered-section");
const ocrPlaceholder = $("#ocr-placeholder");
const ocrLoading = $("#ocr-loading");

fileInput.addEventListener("change", onFileSelected);

async function onFileSelected(e) {
  const file = e.target.files[0];
  if (!file) return;

  uploadProgress.classList.remove("hidden");
  const label = document.querySelector(".upload-label");
  if (label) label.classList.add("hidden");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    state.fileId = data.file_id;
    state.filename = data.filename;
    state.totalPages = data.total_pages;
    state.currentPage = 1;
    state.ocrCache = {};

    viewer.classList.remove("hidden");
    filenameDisplay.textContent = data.filename;
    totalPagesEl.textContent = data.total_pages;
    updatePage();
    updateButtons();
  } catch (err) {
    alert("Errore caricamento: " + err.message);
  } finally {
    uploadProgress.classList.add("hidden");
    if (label) label.classList.remove("hidden");
    fileInput.value = "";
  }
}

function updatePage() {
  currentPageEl.textContent = state.currentPage;
  if (state.fileId) {
    pageImage.src = `${window.location.origin}/api/pages/${state.fileId}/${state.currentPage}`;
    pageImage.alt = `Pagina ${state.currentPage}`;
  }
  updateButtons();

  if (state.ocrCache[state.currentPage]) {
    showOcrResult(state.ocrCache[state.currentPage]);
  } else {
    clearOcrResult();
  }
}

function updateButtons() {
  btnPrev.disabled = state.currentPage <= 1;
  btnNext.disabled = state.currentPage >= state.totalPages;
}

btnPrev.addEventListener("click", () => {
  if (state.currentPage > 1) {
    state.currentPage--;
    updatePage();
  }
});

btnNext.addEventListener("click", () => {
  if (state.currentPage < state.totalPages) {
    state.currentPage++;
    updatePage();
  }
});

document.addEventListener("keydown", (e) => {
  if (!state.fileId) return;
  if (e.key === "ArrowLeft") btnPrev.click();
  if (e.key === "ArrowRight") btnNext.click();
});

btnOcrPage.addEventListener("click", async () => {
  if (!state.fileId) return;
  if (state.ocrCache[state.currentPage]) {
    showOcrResult(state.ocrCache[state.currentPage]);
    return;
  }

  ocrLoading.classList.remove("hidden");
  ocrPlaceholder.classList.add("hidden");
  ocrRawSection.classList.add("hidden");
  ocrRenderedSection.classList.add("hidden");

  try {
    const res = await fetch(`${API}/ocr/${state.fileId}/${state.currentPage}`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.ocrCache[state.currentPage] = data.markdown;
    showOcrResult(data.markdown);
  } catch (err) {
    alert("Errore OCR: " + err.message);
    clearOcrResult();
  } finally {
    ocrLoading.classList.add("hidden");
  }
});

btnOcrAll.addEventListener("click", async () => {
  if (!state.fileId) return;

  const origPage = state.currentPage;
  btnOcrAll.disabled = true;
  btnOcrAll.textContent = "OCR in corso...";

  for (let p = 1; p <= state.totalPages; p++) {
    if (state.ocrCache[p]) continue;

    state.currentPage = p;
    updatePage();

    ocrLoading.classList.remove("hidden");
    ocrPlaceholder.classList.add("hidden");
    ocrRawSection.classList.add("hidden");
    ocrRenderedSection.classList.add("hidden");

    try {
      const res = await fetch(`${API}/ocr/${state.fileId}/${p}`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        state.ocrCache[p] = data.markdown;
        if (p === state.currentPage) showOcrResult(data.markdown);
      }
    } catch {
      // skip failed pages
    } finally {
      ocrLoading.classList.add("hidden");
    }
  }

  state.currentPage = origPage;
  updatePage();
  btnOcrAll.disabled = false;
  btnOcrAll.textContent = "OCR tutto";
});

btnDownload.addEventListener("click", () => {
  const text = state.ocrCache[state.currentPage];
  if (!text) return;
  const blob = new Blob([text], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const baseName = state.filename.replace(/\.[^/.]+$/, "");
  a.href = url;
  a.download = `${baseName}_pagina_${state.currentPage}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  btnDownload.textContent = "Scaricato!";
  setTimeout(() => { btnDownload.textContent = "Scarica"; }, 1500);
});

btnCopy.addEventListener("click", async () => {
  const text = state.ocrCache[state.currentPage];
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    btnCopy.textContent = "Copiato!";
    setTimeout(() => { btnCopy.textContent = "Copia"; }, 1500);
  } catch {
    alert("Copia fallita");
  }
});

function showOcrResult(markdown) {
  ocrRaw.textContent = markdown;
  ocrContent.innerHTML = marked.parse(markdown);
  ocrRawSection.classList.remove("hidden");
  ocrRenderedSection.classList.remove("hidden");
  ocrPlaceholder.classList.add("hidden");
  ocrLoading.classList.add("hidden");
}

function clearOcrResult() {
  ocrRaw.textContent = "";
  ocrContent.innerHTML = "";
  ocrRawSection.classList.add("hidden");
  ocrRenderedSection.classList.add("hidden");
  ocrPlaceholder.classList.remove("hidden");
  ocrLoading.classList.add("hidden");
}

const divider = $(".divider");
let isDragging = false;

divider.addEventListener("mousedown", (e) => {
  isDragging = true;
  document.body.style.cursor = "col-resize";
  document.body.style.userSelect = "none";
});

document.addEventListener("mousemove", (e) => {
  if (!isDragging) return;
  const split = $("#split-view");
  const rect = split.getBoundingClientRect();
  const pct = ((e.clientX - rect.left) / rect.width) * 100;
  const clamped = Math.max(20, Math.min(80, pct));
  const panels = split.querySelectorAll(".panel");
  panels[0].style.flex = `${clamped}%`;
  panels[1].style.flex = `${100 - clamped}%`;
});

document.addEventListener("mouseup", () => {
  if (isDragging) {
    isDragging = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }
});
