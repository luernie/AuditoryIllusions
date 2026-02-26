"""
Audio Perception Ranker
=======================
Install:  pip install pywebview
Run:      python audio_ranker.py

Set AUDIO_FOLDER below to point at your audio files.
"""

import webview
import base64
from pathlib import Path
from datetime import date

# ── CONFIG ────────────────────────────────────────────────────────────────────
AUDIO_FOLDER = "./audio"          # <-- change this to your folder path
WINDOW_TITLE = "Pitch Perception Ranker"
WINDOW_W, WINDOW_H = 980, 820
# ─────────────────────────────────────────────────────────────────────────────

AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.aac', '.m4a'}
MIME = {
    '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.flac': 'audio/flac',
    '.ogg': 'audio/ogg', '.aac': 'audio/aac', '.m4a': 'audio/mp4',
}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pitch Perception Ranker</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0d0d0f; --surface:#141418; --border:#2a2a32;
    --accent:#c8f060; --text:#e8e8ec; --muted:#666672;
    --neg:#ff6b6b; --pos:#6bffb8; --mid:#ffd166;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'DM Mono',monospace; min-height:100vh; padding:36px 24px 80px; }

  header { max-width:860px; margin:0 auto 36px; border-bottom:1px solid var(--border); padding-bottom:20px; display:flex; justify-content:space-between; align-items:flex-end; }
  header h1 { font-family:'Instrument Serif',serif; font-size:2rem; font-weight:400; letter-spacing:-0.02em; }
  header h1 span { color:var(--accent); font-style:italic; }
  .subtitle { color:var(--muted); font-size:0.7rem; letter-spacing:0.08em; text-transform:uppercase; margin-top:4px; }
  .folder-tag { font-size:0.7rem; color:var(--muted); background:var(--surface); border:1px solid var(--border); border-radius:4px; padding:4px 10px; max-width:280px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .folder-tag span { color:var(--accent); }

  .cards-container { max-width:860px; margin:0 auto; display:flex; flex-direction:column; gap:10px; }
  .card {
    background:var(--surface); border:1px solid var(--border); border-radius:10px;
    padding:16px 20px; display:grid; grid-template-columns:28px 1fr; align-items:center;
    gap:14px; animation:slideIn 0.25s ease forwards; opacity:0;
  }
  .card:hover { border-color:#3a3a46; }
  .rank-badge { font-size:0.65rem; color:var(--muted); text-align:center; }
  .card-body { display:flex; flex-direction:column; gap:10px; }
  .card-top { display:flex; align-items:center; gap:10px; }
  .play-btn {
    background:none; border:1px solid var(--border); color:var(--text);
    width:32px; height:32px; border-radius:50%; cursor:pointer;
    display:flex; align-items:center; justify-content:center; font-size:0.7rem; flex-shrink:0;
    transition:border-color 0.15s, background 0.15s;
  }
  .play-btn:hover { border-color:var(--accent); color:var(--accent); }
  .play-btn.playing { border-color:var(--accent); background:rgba(200,240,96,0.1); color:var(--accent); }
  .filename { font-size:0.78rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:560px; }
  .slider-row { display:flex; align-items:center; gap:10px; }
  .lbl { font-size:0.62rem; white-space:nowrap; }
  .lbl.neg { color:var(--neg); } .lbl.pos { color:var(--pos); }
  input[type=range] {
    -webkit-appearance:none; flex:1; height:4px; border-radius:2px; outline:none; cursor:pointer;
    background:linear-gradient(to right,var(--neg),var(--mid),var(--pos));
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance:none; width:18px; height:18px; border-radius:50%;
    background:var(--text); border:2px solid var(--bg); box-shadow:0 0 0 1px var(--accent); cursor:grab;
    transition:transform 0.1s;
  }
  input[type=range]:active::-webkit-slider-thumb { transform:scale(1.2); cursor:grabbing; }
  .score-val { font-size:0.75rem; min-width:34px; text-align:right; font-variant-numeric:tabular-nums; }
  .score-val.neg{color:var(--neg);} .score-val.pos{color:var(--pos);} .score-val.zero{color:var(--muted);}

  .footer { max-width:860px; margin:36px auto 0; display:flex; align-items:center; justify-content:space-between; padding-top:18px; border-top:1px solid var(--border); }
  .progress { font-size:0.75rem; color:var(--muted); }
  .progress span { color:var(--accent); }
  .export-btn {
    background:var(--accent); color:#0d0d0f; border:none; padding:10px 22px;
    border-radius:6px; font-family:'DM Mono',monospace; font-size:0.78rem; font-weight:500; cursor:pointer; transition:background 0.15s;
  }
  .export-btn:hover { background:#d4f570; }
  .empty { max-width:860px; margin:60px auto; text-align:center; color:var(--muted); font-size:0.8rem; }

  @keyframes slideIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
</style>
</head>
<body>

<header>
  <div>
    <h1>Pitch Perception <span>Ranker</span></h1>
    <p class="subtitle">Psychoacoustics · Drag sliders to rank · Export results</p>
  </div>
  <div class="folder-tag" id="folderLabel">loading...</div>
</header>

<div class="cards-container" id="cards">
  <div class="empty">Loading audio files...</div>
</div>

<div class="footer">
  <div class="progress"><span id="ratedCount">0</span> / <span id="totalCount">0</span> rated</div>
  <button class="export-btn" onclick="exportCSV()">Export Results ↓</button>
</div>

<script>
  let items = [];
  let currentAudio = null;
  let currentBtn = null;

  async function init() {
    const data = await pywebview.api.get_files();
    document.getElementById('folderLabel').textContent = data.folder;
    items = data.files.map(f => ({ filename: f, score: 0 }));
    document.getElementById('totalCount').textContent = items.length;
    renderCards();
  }

  function renderCards() {
    const container = document.getElementById('cards');
    container.innerHTML = '';
    const sorted = [...items].sort((a, b) => a.score - b.score);

    sorted.forEach((item, idx) => {
      const sc = item.score;
      const cls = sc < 0 ? 'neg' : sc > 0 ? 'pos' : 'zero';
      const sign = sc > 0 ? '+' : '';

      const card = document.createElement('div');
      card.className = 'card';
      card.style.animationDelay = (idx * 30) + 'ms';
      card.innerHTML = `
        <div class="rank-badge">${idx + 1}</div>
        <div class="card-body">
          <div class="card-top">
            <button class="play-btn">&#9654;</button>
            <span class="filename" title="${item.filename}">${item.filename}</span>
          </div>
          <div class="slider-row">
            <span class="lbl neg">-10 decreasing</span>
            <input type="range" min="-10" max="10" step="1" value="${sc}">
            <span class="lbl pos">+10 increasing</span>
            <span class="score-val ${cls}">${sign}${sc}</span>
          </div>
        </div>`;

      card.querySelector('.play-btn').addEventListener('click', async function () {
        if (currentAudio && !currentAudio.paused) {
          currentAudio.pause(); currentAudio.currentTime = 0;
          if (currentBtn) { currentBtn.innerHTML = '&#9654;'; currentBtn.classList.remove('playing'); }
          if (currentBtn === this) { currentAudio = null; currentBtn = null; return; }
        }
        const result = await pywebview.api.get_audio(item.filename);
        if (!result) return;
        currentAudio = new Audio(result.data_url);
        currentBtn = this;
        this.innerHTML = '&#9646;&#9646;'; this.classList.add('playing');
        currentAudio.play();
        currentAudio.onended = () => {
          this.innerHTML = '&#9654;'; this.classList.remove('playing');
          currentAudio = null; currentBtn = null;
        };
      });

      card.querySelector('input[type=range]').addEventListener('input', function () {
        item.score = parseInt(this.value);
        const v = item.score;
        const scoreEl = this.closest('.slider-row').querySelector('.score-val');
        scoreEl.textContent = (v > 0 ? '+' : '') + v;
        scoreEl.className = 'score-val ' + (v < 0 ? 'neg' : v > 0 ? 'pos' : 'zero');
        updateProgress();
        clearTimeout(window._t);
        window._t = setTimeout(renderCards, 350);
      });

      container.appendChild(card);
    });

    updateProgress();
  }

  function updateProgress() {
    document.getElementById('ratedCount').textContent = items.filter(i => i.score !== 0).length;
  }

  async function exportCSV() {
    const sorted = [...items].sort((a, b) => a.score - b.score);
    const rows = [['Rank','Filename','Score'], ...sorted.map((it, i) => [i+1, it.filename, it.score])];
    const csv = rows.map(r => r.join(',')).join('\n');
    await pywebview.api.save_csv(csv);
  }

  window.addEventListener('pywebviewready', init);
</script>
</body>
</html>
"""


class API:
    def get_files(self):
        folder = Path(AUDIO_FOLDER).resolve()
        files = sorted([
            f.name for f in folder.iterdir()
            if f.suffix.lower() in AUDIO_EXTENSIONS
        ])
        return {"folder": str(folder), "files": files}

    def get_audio(self, filename):
        path = Path(AUDIO_FOLDER).resolve() / filename
        if not path.exists():
            return None
        mime = MIME.get(path.suffix.lower(), 'audio/octet-stream')
        data = base64.b64encode(path.read_bytes()).decode()
        return {"data_url": f"data:{mime};base64,{data}"}

    def save_csv(self, csv_content):
        out = Path(AUDIO_FOLDER).resolve() / f"rankings_{date.today()}.csv"
        out.write_text(csv_content)
        webview.windows[0].evaluate_js(f"alert('Saved to: {out}')")


if __name__ == '__main__':
    api = API()
    window = webview.create_window(
        WINDOW_TITLE,
        html=HTML,
        width=WINDOW_W,
        height=WINDOW_H,
        resizable=True,
        js_api=api,
    )
    webview.start()