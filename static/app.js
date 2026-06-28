const state = { phase: 'idle', files: [], uploadId: null, results: [] };
const els = {
  signinPage: document.querySelector('#signinPage'), signinForm: document.querySelector('#signinForm'), appShell: document.querySelector('#appShell'), signoutBtn: document.querySelector('#signoutBtn'),
  dropzone: document.querySelector('#dropzone'), fileInput: document.querySelector('#fileInput'), browseBtn: document.querySelector('#browseBtn'), fileList: document.querySelector('#fileList'),
  analyzeBtn: document.querySelector('#analyzeBtn'), jobDescription: document.querySelector('#jobDescription'), message: document.querySelector('#message'), statePill: document.querySelector('#statePill'),
  grid: document.querySelector('#candidateGrid'), resultCount: document.querySelector('#resultCount'), statFiles: document.querySelector('#statFiles'), statTop: document.querySelector('#statTop'), statGems: document.querySelector('#statGems'),
  details: document.querySelector('#detailsPanel'), detailsContent: document.querySelector('#detailsContent'), closePanel: document.querySelector('#closePanel'), panelScrim: document.querySelector('#panelScrim')
};

function showApp() { els.signinPage.classList.add('hidden'); els.appShell.classList.remove('hidden'); }
function showSignin() { els.appShell.classList.add('hidden'); els.signinPage.classList.remove('hidden'); closeDetails(); }

els.signinForm.addEventListener('submit', event => { event.preventDefault(); localStorage.setItem('talentscout_signed_in', 'true'); showApp(); });
els.signoutBtn.addEventListener('click', () => { localStorage.removeItem('talentscout_signed_in'); showSignin(); });
if (localStorage.getItem('talentscout_signed_in') === 'true') showApp();

function setPhase(phase) { state.phase = phase; els.statePill.innerHTML = `<i class="ph ph-circle-notch"></i>${phase}`; }
function setMessage(text) { els.message.textContent = text; }
function fileKey(file) { return `${file.name}-${file.size}-${file.lastModified}`; }

function renderFiles() {
  els.fileList.innerHTML = state.files.map(file => `<span class="file-chip">${file.name}</span>`).join('');
  els.statFiles.textContent = state.files.length;
}

function acceptFiles(files) {
  const existing = new Set(state.files.map(fileKey));
  const incoming = [...files].filter(file => !existing.has(fileKey(file)));
  state.files = [...state.files, ...incoming];
  state.uploadId = null;
  els.fileInput.value = '';
  renderFiles();
  setPhase('idle');
  setMessage(`${state.files.length} resume(s) queued to compare against this job description.`);
}

els.browseBtn.addEventListener('click', () => els.fileInput.click());
els.fileInput.addEventListener('change', event => acceptFiles(event.target.files));
['dragenter', 'dragover'].forEach(name => els.dropzone.addEventListener(name, event => { event.preventDefault(); els.dropzone.classList.add('dragover'); }));
['dragleave', 'drop'].forEach(name => els.dropzone.addEventListener(name, event => { event.preventDefault(); els.dropzone.classList.remove('dragover'); }));
els.dropzone.addEventListener('drop', event => acceptFiles(event.dataTransfer.files));
els.closePanel.addEventListener('click', closeDetails);
els.panelScrim.addEventListener('click', closeDetails);

function closeDetails() { els.details.classList.remove('open'); els.panelScrim.classList.remove('open'); }

async function uploadFiles() {
  const form = new FormData();
  state.files.forEach(file => form.append('files', file));
  setPhase('uploading');
  setMessage(`Uploading ${state.files.length} resume(s) for batch screening...`);
  const response = await fetch('/api/upload', { method: 'POST', body: form });
  if (!response.ok) throw new Error((await response.json()).detail || 'Upload failed');
  const data = await response.json();
  state.uploadId = data.uploadId;
  return data;
}

async function analyze() {
  if (!state.files.length) { setMessage('Please choose at least one resume.'); return; }
  if (els.jobDescription.value.trim().length < 20) { setMessage('Please paste a fuller job description first.'); return; }
  try {
    els.analyzeBtn.disabled = true;
    await uploadFiles();
    setPhase('parsing');
    setMessage(`Extracting text from ${state.files.length} resume(s)...`);
    await new Promise(resolve => setTimeout(resolve, 350));
    setPhase('analyzing');
    setMessage('Comparing every resume against the same job description and ranking by match...');
    const response = await fetch('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uploadId: state.uploadId, jobDescription: els.jobDescription.value })
    });
    if (!response.ok) throw new Error((await response.json()).detail || 'Analysis failed');
    state.results = await response.json();
    setPhase('results_ready');
    setMessage(`${state.results.length} resume(s) ranked by job-description match.`);
    renderResults();
  } catch (error) {
    setPhase('idle');
    setMessage(error.message);
  } finally {
    els.analyzeBtn.disabled = false;
  }
}

els.analyzeBtn.addEventListener('click', analyze);

function renderResults() {
  els.resultCount.textContent = `${state.results.length} candidate(s), ranked highest match first`;
  els.statTop.textContent = state.results[0]?.score ?? '--';
  els.statGems.textContent = state.results.filter(candidate => candidate.isHiddenGem).length;
  els.grid.innerHTML = state.results.map((candidate, index) => `
    <article class="candidate-card" data-id="${candidate.id}">
      <div class="candidate-top"><div><span class="tier">#${index + 1} · Tier ${candidate.tier}</span><h3>${candidate.name}</h3><p>${candidate.currentRole} · ${candidate.experience}</p></div><div class="score">${candidate.score}</div></div>
      <p>${candidate.summary}</p>
      <div class="skills">${candidate.skills.matched.slice(0, 4).map(skill => `<span class="skill">${skill}</span>`).join('')}${candidate.isHiddenGem ? '<span class="skill">hidden-gem</span>' : ''}</div>
    </article>
  `).join('');
  document.querySelectorAll('.candidate-card').forEach(card => card.addEventListener('click', () => showDetails(Number(card.dataset.id))));
}

function showDetails(id) {
  const candidate = state.results.find(item => item.id === id);
  if (!candidate) return;
  const bars = Object.entries(candidate.scoreBreakdown).map(([key, value]) => `<div><strong>${label(key)}: ${value}</strong><div class="bar"><span style="width:${value}%"></span></div></div>`).join('');
  els.detailsContent.innerHTML = `<h2>${candidate.name}</h2><p>${candidate.filename}</p><div class="score">${candidate.score}</div><h3>${candidate.currentRole}</h3><p>${candidate.location} · ${candidate.experience}</p><p>${candidate.summary}</p><h3>Matched skills</h3><div class="skills">${candidate.skills.matched.map(skill => `<span class="skill">${skill}</span>`).join('') || '<span class="skill">None</span>'}</div><h3>Missing skills</h3><div class="skills">${candidate.skills.missing.map(skill => `<span class="skill">${skill}</span>`).join('') || '<span class="skill">None</span>'}</div><div class="breakdown">${bars}</div><h3>Insights</h3><p>Education: ${candidate.insights.education}</p><p>Previous companies: ${candidate.insights.prevCompanies}</p><h3>Hidden Gem</h3><p>${candidate.hiddenGemReason}</p>`;
  els.details.classList.add('open');
  els.panelScrim.classList.add('open');
}

function label(key) { return key.replace(/[A-Z]/g, match => ' ' + match).replace(/^./, char => char.toUpperCase()); }
