(function () {
  'use strict';

  const app = document.getElementById('bingo-app');
  if (!app) return;

  const role = app.dataset.role;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const POLL_MS = 1500;
  const STAGE_TEXT = {
    waiting: 'Esperando a que empiece la partida',
    linea: 'Jugando a línea',
    bingo: 'Jugando a bingo',
    finished: 'Partida terminada',
  };
  const PRIZE_TEXT = { linea: 'Línea', bingo: 'Bingo' };

  let state = JSON.parse(document.getElementById('initial-state').textContent);
  let gameId = state.game_id;
  let pauseEndsAt = null;
  let autoTimer = null;
  let drawing = false;
  const pendingMarks = new Map();

  const $ = (id) => document.getElementById(id);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function post(url, data) {
    let response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf },
        body: new URLSearchParams(data || {}),
        credentials: 'same-origin',
      });
    } catch (e) {
      return { ok: false, json: { message: 'Sin conexión. Inténtalo de nuevo.' } };
    }
    if (response.status === 404 || (role === 'player' && response.status === 403)) {
      window.location.reload();
    }
    let json = null;
    try { json = await response.json(); } catch (e) { json = null; }
    return { ok: response.ok && !!json && json.ok, json: json || {} };
  }

  let messageTimer = null;
  function showMessage(text, kind) {
    const box = $('message');
    box.textContent = text || '';
    box.className = 'claim-message' + (kind ? ' ' + kind : '');
    clearTimeout(messageTimer);
    if (text) messageTimer = setTimeout(() => { box.textContent = ''; }, 5000);
  }

  // Shared rendering

  // What the last render showed; null until the first render sets the baseline.
  let renderedGameId = null;
  let renderedCount = 0;

  // Restart the CSS animation tied to .is-new, even on an element that already has it.
  function playNew(node) {
    if (!node) return;
    node.classList.remove('is-new');
    void node.offsetWidth;
    node.classList.add('is-new');
  }

  document.addEventListener('animationend', (event) => event.target.classList.remove('is-new'));

  function updateStripHint() {
    const strip = $('drawn-strip');
    if (!strip) return;
    strip.classList.toggle('has-more', strip.scrollLeft + strip.clientWidth < strip.scrollWidth - 1);
  }

  function renderStrip(strip, sameGame) {
    const count = state.drawn.length;
    if (sameGame && count === renderedCount) return;
    if (sameGame && count > renderedCount) {
      let newest = null;
      state.drawn.slice(renderedCount).forEach((n) => {
        newest = el('span', 'ball ball-small', n);
        strip.prepend(newest);
      });
      playNew(newest);
      return;
    }
    strip.replaceChildren(...state.drawn.slice().reverse().map((n) => el('span', 'ball ball-small', n)));
  }

  function renderBalls() {
    const sameGame = renderedGameId === state.game_id;
    const newBall = sameGame && state.drawn.length > renderedCount;

    $('last-ball').textContent = state.last === null ? '–' : state.last;
    if (newBall) playNew($('last-ball'));
    if (newBall && role === 'host') announceBall(state.last);
    $('stage-text').textContent = STAGE_TEXT[state.stage];
    $('drawn-count').textContent = state.drawn.length;

    const strip = $('drawn-strip');
    if (strip) renderStrip(strip, sameGame);
    const board = $('board');
    if (board) {
      const drawn = new Set(state.drawn);
      board.querySelectorAll('.board-cell').forEach((cell) => {
        const n = Number(cell.dataset.number);
        cell.classList.toggle('drawn', drawn.has(n));
        cell.classList.toggle('last', n === state.last);
        if (newBall && n === state.last) playNew(cell);
      });
      $('balls-left').textContent = state.balls_left;
    }

    renderedGameId = state.game_id;
    renderedCount = state.drawn.length;
    updateStripHint();
  }

  function winnerList(items, withNumbers) {
    return items.map((w) => {
      const li = el('li');
      li.appendChild(el('strong', '', w.nickname));
      if (withNumbers) li.appendChild(el('span', 'winner-numbers', ' ' + w.numbers.join(' · ')));
      return li;
    });
  }

  function renderWinners() {
    const panel = $('winners');
    const parts = [];
    if (state.stage === 'finished') parts.push(el('div', 'winners-title', '¡Partida terminada!'));
    ['linea', 'bingo'].forEach((prize) => {
      const winners = state.winners[prize];
      if (!winners.length) return;
      const row = el('div', 'winners-row');
      row.appendChild(el('span', 'winners-prize', PRIZE_TEXT[prize] + ': '));
      row.appendChild(el('span', '', winners.map((w) => w.nickname).join(', ')));
      parts.push(row);
    });
    panel.replaceChildren(...parts);
  }

  function renderPause() {
    const overlay = $('pause');
    if (!state.pause) {
      overlay.hidden = true;
      pauseEndsAt = null;
      return;
    }
    const prize = state.pause.prize;
    $('pause-title').textContent = '¡' + PRIZE_TEXT[prize] + '!';
    $('pause-winners').replaceChildren(...winnerList(state.winners[prize], true));
    pauseEndsAt = Date.now() + state.pause.remaining_ms;
    overlay.hidden = false;
    animatePause();
  }

  function animatePause() {
    if (pauseEndsAt === null) return;
    const left = Math.max(0, pauseEndsAt - Date.now());
    $('pause-bar').style.width = (100 * left / state.pause.total_ms) + '%';
    if (left > 0) requestAnimationFrame(animatePause);
    else pollSoon();
  }

  // Player

  function buildCard() {
    const table = $('card');
    const rows = (state.me.card || []).map((row) => {
      const tr = el('tr');
      row.forEach((n) => {
        const td = el('td', n === null ? 'cell blank' : 'cell', n === null ? '' : n);
        if (n !== null) td.dataset.number = n;
        tr.appendChild(td);
      });
      return tr;
    });
    table.replaceChildren(...rows);
  }

  function renderMarks() {
    const marks = new Set(state.me.marks);
    pendingMarks.forEach((marked, n) => { if (marked) marks.add(n); else marks.delete(n); });
    $('card').querySelectorAll('.cell[data-number]').forEach((cell) => {
      cell.classList.toggle('marked', marks.has(Number(cell.dataset.number)));
    });
  }

  function renderPlayer() {
    if (state.me.removed) { window.location.reload(); return; }
    if (state.game_id !== gameId) {
      gameId = state.game_id;
      pendingMarks.clear();
      buildCard();
      showMessage('¡Nueva partida! Tienes un cartón nuevo.', 'info');
    }
    renderMarks();
    $('claim-linea').disabled = state.stage !== 'linea';
    $('claim-bingo').disabled = state.stage !== 'bingo';
  }

  function setupPlayer() {
    $('card').addEventListener('click', async (event) => {
      const cell = event.target.closest('.cell[data-number]');
      if (!cell || state.stage === 'finished') return;
      const n = Number(cell.dataset.number);
      const marked = !cell.classList.contains('marked');
      pendingMarks.set(n, marked);
      renderMarks();
      const result = await post(app.dataset.markUrl, { number: n, marked: marked ? '1' : '0' });
      if (pendingMarks.get(n) === marked) pendingMarks.delete(n);
      if (result.ok) state.me.marks = result.json.marks;
      else showMessage(result.json.message, 'error');
      renderMarks();
    });

    document.querySelectorAll('[data-prize]').forEach((button) => {
      button.addEventListener('click', async () => {
        button.disabled = true;
        const result = await post(app.dataset.claimUrl, { prize: button.dataset.prize });
        if (result.ok) {
          showMessage(button.dataset.prize === 'linea' ? '¡Línea comprobada!' : '¡Bingo comprobado!', 'success');
          update(result.json.state);
        } else {
          showMessage(result.json.message, 'error');
          render();
        }
      });
    });
  }

  // Sound (host screen only)

  const SOUND_KEY = 'bingo.sound';
  const BALL_SOUND_KEY = 'bingo.ballSound';
  const CALL = { rate: 0.9, gapParts: 100, gapDigits: 200 };
  const UNITS = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve'];
  const TEENS = ['diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve'];
  const TWENTIES = ['veinte', 'veintiuno', 'veintidós', 'veintitrés', 'veinticuatro', 'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve'];
  const TENS = { 3: 'treinta', 4: 'cuarenta', 5: 'cincuenta', 6: 'sesenta', 7: 'setenta', 8: 'ochenta', 9: 'noventa' };

  let soundOn = false;
  let ballSoundOn = false;
  let audioCtx = null;
  let master = null;
  let noiseBuffer = null;
  let callId = 0;
  // Last pause that had its win sound; undefined until the first render sets the baseline.
  let soundedPause;

  function numberName(n) {
    if (n < 10) return UNITS[n];
    if (n < 20) return TEENS[n - 10];
    if (n < 30) return TWENTIES[n - 20];
    const unit = n % 10;
    return unit === 0 ? TENS[Math.floor(n / 10)] : TENS[Math.floor(n / 10)] + ' y ' + UNITS[unit];
  }

  function readSetting(key) {
    try { return window.localStorage.getItem(key) === 'on'; } catch (e) { return false; }
  }

  function saveSetting(key, on) {
    try { window.localStorage.setItem(key, on ? 'on' : 'off'); } catch (e) { /* storage blocked */ }
  }

  function audioReady() {
    return soundOn && audioCtx !== null && audioCtx.state === 'running';
  }

  // Must run inside a user gesture the first time, or the browser keeps audio blocked.
  function unlockAudio() {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return Promise.resolve();
      audioCtx = new Ctx();
      audioCtx.addEventListener('statechange', renderSoundToggle);
    }
    return audioCtx.state === 'running' ? Promise.resolve() : audioCtx.resume().catch(() => {});
  }

  function output() {
    if (!master) {
      master = audioCtx.createGain();
      master.connect(audioCtx.destination);
    }
    return master;
  }

  function stopSound() {
    callId += 1;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (master) { master.disconnect(); master = null; }
  }

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function spanishVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    const lang = (v) => v.lang.replace('_', '-').toLowerCase();
    return voices.find((v) => lang(v) === 'es-es') || voices.find((v) => lang(v).startsWith('es')) || null;
  }

  function say(text, voice) {
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.rate = CALL.rate;
      utterance.onend = resolve;
      utterance.onerror = resolve;
      window.speechSynthesis.speak(utterance);
    });
  }

  // Speaks the parts in order; stops as soon as a newer call starts.
  async function speakParts(parts, gaps, id) {
    const voice = spanishVoice();
    if (!voice) return;
    for (let i = 0; i < parts.length; i += 1) {
      if (gaps[i]) await wait(gaps[i]);
      if (id !== callId) return;
      await say(parts[i], voice);
    }
  }

  async function callBall(n) {
    callId += 1;
    const id = callId;
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (ballSoundOn) {
      playPop();
      await wait(150);
      if (id !== callId) return;
    }
    const parts = n < 10 ? [numberName(n)] : [numberName(n), UNITS[Math.floor(n / 10)], UNITS[n % 10]];
    await speakParts(parts, [0, CALL.gapParts, CALL.gapDigits], id);
  }

  function tone(freq, start, duration, type, volume) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(volume, start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    osc.connect(gain).connect(output());
    osc.start(start);
    osc.stop(start + duration + 0.05);
  }

  function playBeep() {
    const now = audioCtx.currentTime;
    tone(660, now, 0.15, 'sine', 0.3);
    tone(880, now + 0.17, 0.2, 'sine', 0.3);
  }

  function playPop() {
    const now = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.setValueAtTime(900, now);
    osc.frequency.exponentialRampToValueAtTime(180, now + 0.12);
    gain.gain.setValueAtTime(0.4, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.14);
    osc.connect(gain).connect(output());
    osc.start(now);
    osc.stop(now + 0.15);
  }

  // Many short filtered noise bursts at random times sound like a crowd clapping.
  function playApplause(start, duration) {
    if (!noiseBuffer) {
      noiseBuffer = audioCtx.createBuffer(1, audioCtx.sampleRate, audioCtx.sampleRate);
      const data = noiseBuffer.getChannelData(0);
      for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
    }
    const claps = Math.round(duration * 35);
    for (let i = 0; i < claps; i += 1) {
      const at = Math.random() * duration;
      const loudness = Math.min(1, at / 0.3, (duration - at) / (duration * 0.4));
      const t = start + at;
      const src = audioCtx.createBufferSource();
      const filter = audioCtx.createBiquadFilter();
      const gain = audioCtx.createGain();
      src.buffer = noiseBuffer;
      filter.type = 'bandpass';
      filter.frequency.value = 900 + Math.random() * 1600;
      filter.Q.value = 1.2;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(Math.max(0.001, 0.5 * loudness), t + 0.003);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.05 + Math.random() * 0.06);
      src.connect(filter).connect(gain).connect(output());
      src.start(t, Math.random() * 0.8, 0.15);
    }
  }

  function playFanfare(start) {
    [[523.25, 0, 0.18], [659.25, 0.18, 0.18], [783.99, 0.36, 0.18], [1046.5, 0.54, 0.7]].forEach(([freq, at, length]) => {
      tone(freq, start + at, length, 'triangle', 0.35);
      tone(freq * 2, start + at, length, 'sine', 0.08);
    });
  }

  function playWin(prize) {
    const now = audioCtx.currentTime;
    if (prize === 'bingo') {
      playFanfare(now);
      playApplause(now + 0.9, 4);
    } else {
      playApplause(now, 2.5);
    }
  }

  function playTest() {
    stopSound();
    playBeep();
    const id = callId;
    wait(450).then(() => speakParts(['Sonido activado'], [0], id));
  }

  function announceBall(n) {
    if (audioReady()) callBall(n);
  }

  function checkWinSound() {
    const key = state.pause ? state.game_id + ':' + state.pause.prize : null;
    if (soundedPause === undefined) { soundedPause = key; return; }
    if (key === null || key === soundedPause) return;
    soundedPause = key;
    if (audioReady()) playWin(state.pause.prize);
  }

  function renderSoundToggle() {
    const button = $('sound-toggle');
    const playing = audioReady();
    if (!soundOn) button.textContent = '🔇 Activar sonido';
    else if (playing) button.textContent = '🔊 Sonido activado';
    else button.textContent = '🔈 Toca para activar sonido';
    button.setAttribute('aria-pressed', playing ? 'true' : 'false');
    button.classList.toggle('btn-light', playing);
    button.classList.toggle('btn-outline-light', !playing);
  }

  function setupSound() {
    soundOn = readSetting(SOUND_KEY);
    ballSoundOn = readSetting(BALL_SOUND_KEY);
    $('ball-sound').checked = ballSoundOn;
    renderSoundToggle();

    $('sound-toggle').addEventListener('click', async () => {
      if (audioReady()) {
        soundOn = false;
        saveSetting(SOUND_KEY, false);
        stopSound();
        renderSoundToggle();
        return;
      }
      soundOn = true;
      saveSetting(SOUND_KEY, true);
      await unlockAudio();
      renderSoundToggle();
      if (audioReady()) playTest();
    });

    $('ball-sound').addEventListener('change', (event) => {
      ballSoundOn = event.target.checked;
      saveSetting(BALL_SOUND_KEY, ballSoundOn);
    });

    // Any tap on the page (such as "Sacar bola") unlocks sound that was left on before a reload.
    document.addEventListener('pointerdown', (event) => {
      if (!soundOn || audioReady() || event.target.closest('#sound-toggle')) return;
      unlockAudio().then(renderSoundToggle);
    });
  }

  // Host

  function renderPlayers() {
    const list = $('players');
    list.replaceChildren(...state.players.map((p) => {
      const li = el('li');
      li.appendChild(el('span', '', p.nickname));
      const remove = el('button', 'btn btn-sm btn-link text-danger remove-btn', 'Quitar');
      remove.type = 'button';
      remove.addEventListener('click', async () => {
        if (!window.confirm('¿Quitar a ' + p.nickname + ' de la sala?')) return;
        const result = await post(app.dataset.removeUrl.replace(/\/0\/$/, '/' + p.id + '/'));
        if (result.ok) update(result.json.state); else showMessage(result.json.message, 'error');
      });
      li.appendChild(remove);
      return li;
    }));
    $('player-count').textContent = state.players.length;
  }

  function scheduleAutoDraw() {
    clearTimeout(autoTimer);
    autoTimer = null;
    if (state.next_auto_draw_ms !== null && state.next_auto_draw_ms !== undefined) {
      autoTimer = setTimeout(drawBall, state.next_auto_draw_ms);
    }
  }

  async function drawBall() {
    if (drawing) return;
    drawing = true;
    const result = await post(app.dataset.drawUrl, { seen: state.drawn.length });
    drawing = false;
    if (result.ok) update(result.json.state);
    else showMessage(result.json.message, 'error');
  }

  function renderHost() {
    renderPlayers();
    checkWinSound();
    $('draw-btn').disabled = !state.can_draw;
    $('auto-select').value = state.auto_interval ? String(state.auto_interval) : 'off';
    scheduleAutoDraw();
  }

  function setupHost() {
    setupSound();
    $('draw-btn').addEventListener('click', drawBall);

    $('continue-btn').addEventListener('click', async () => {
      const result = await post(app.dataset.continueUrl);
      if (result.ok) update(result.json.state);
    });

    $('auto-select').addEventListener('change', async (event) => {
      const result = await post(app.dataset.autoUrl, { interval: event.target.value });
      if (result.ok) update(result.json.state); else showMessage(result.json.message, 'error');
    });

    $('new-game-btn').addEventListener('click', async () => {
      const inProgress = state.stage === 'linea' || state.stage === 'bingo';
      if (inProgress && !window.confirm('La partida no ha terminado. ¿Empezar una nueva partida?')) return;
      const result = await post(app.dataset.newGameUrl);
      if (result.ok) update(result.json.state);
    });

    // Keep the shared screen awake where the browser allows it.
    async function keepAwake() {
      try { if ('wakeLock' in navigator) await navigator.wakeLock.request('screen'); } catch (e) { /* not allowed */ }
    }
    keepAwake();
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') keepAwake();
    });
  }

  // Loop

  function render() {
    renderBalls();
    renderWinners();
    renderPause();
    if (role === 'host') renderHost(); else renderPlayer();
  }

  function update(newState) {
    state = newState;
    render();
  }

  let pollTimer = null;
  let polling = false;

  function pollSoon() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, 150);
  }

  async function poll() {
    if (polling) return;
    polling = true;
    clearTimeout(pollTimer);
    try {
      const response = await fetch(app.dataset.stateUrl, { credentials: 'same-origin', cache: 'no-store' });
      if (response.status === 404 || response.status === 403) {
        window.location.reload();
        return;
      }
      if (response.ok) update(await response.json());
    } catch (e) { /* offline for a moment; try again */ }
    polling = false;
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, POLL_MS);
  }

  if (role === 'host') setupHost(); else setupPlayer();
  const strip = $('drawn-strip');
  if (strip) {
    strip.addEventListener('scroll', updateStripHint, { passive: true });
    window.addEventListener('resize', updateStripHint);
  }
  render();
  pollTimer = setTimeout(poll, POLL_MS);
})();
