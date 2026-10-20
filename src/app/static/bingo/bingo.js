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
    $('draw-btn').disabled = !state.can_draw;
    $('auto-select').value = state.auto_interval ? String(state.auto_interval) : 'off';
    scheduleAutoDraw();
  }

  function setupHost() {
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
