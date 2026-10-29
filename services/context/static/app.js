'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const state = { key: null, cameras: [], selected: '', snapshotURL: null, generation: 0, controllers: new Set() };
  const presets = {
    live: 'What is the current status for this camera?',
    plate: 'Are any license plate readings available for this camera?',
    color: 'Can the evidence establish the vehicle color or model year?',
    recap: 'Recap activity during the selected time window.'
  };
  const numeric = value => typeof value === 'number' && Number.isFinite(value);
  const text = value => value === null || value === undefined ? '—' : String(value);
  const safeArray = value => Array.isArray(value) ? value : [];
  const when = value => {
    const date = new Date(value);
    return value && !Number.isNaN(date.getTime()) ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'medium' }).format(date) : 'Time unavailable';
  };
  const decimal = value => numeric(value) ? value.toFixed(1) : '—';
  const score = value => numeric(value) && value >= 0 && value <= 1 ? `${Math.round(value * 100)}%` : 'Unavailable';
  const cameraName = id => state.cameras.find(camera => camera.id === id)?.name || id;

  function node(tag, content, className) {
    const element = document.createElement(tag);
    if (content !== undefined && content !== null) element.textContent = String(content);
    if (className) element.className = className;
    return element;
  }

  function alertMessage(message) {
    $('alert').textContent = message || '';
    $('alert').hidden = !message;
  }

  function busy(button, enabled, label) {
    button.disabled = enabled;
    button.classList.toggle('busy', enabled);
    button.setAttribute('aria-busy', String(enabled));
    if (label) button.textContent = label;
  }

  async function request(path, options = {}, key = state.key, binary = false) {
    if (!key) throw new Error('Connect with your access key first.');
    if (!path.startsWith('/v1/')) throw new Error('Unsupported service route.');
    const controller = new AbortController();
    state.controllers.add(controller);
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const headers = { Accept: binary ? 'image/jpeg' : 'application/json', Authorization: `Bearer ${key}` };
      if (options.body) headers['Content-Type'] = 'application/json';
      const response = await fetch(path, { ...options, headers, signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error' });
      if (!response.ok) {
        let body = null;
        try { body = await response.json(); } catch { /* A transport error can lack a JSON body. */ }
        const message = response.status === 401 ? 'That access key was rejected. Check the key and connect again.' : body?.error?.message || `The service could not complete this request (${response.status}).`;
        throw new Error(body?.request_id ? `${message} Reference: ${body.request_id}` : message);
      }
      if (binary) {
        if (response.headers.get('Content-Type')?.split(';')[0] !== 'image/jpeg') throw new Error('The service did not return a valid JPEG snapshot.');
        const image = await response.blob();
        if (!image.size || image.size > 8 * 1024 * 1024) throw new Error('The snapshot is empty or exceeds the image size limit.');
        return image;
      }
      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The request was canceled or timed out. Try a shorter window or refresh the camera.');
      throw error;
    } finally {
      clearTimeout(timeout);
      state.controllers.delete(controller);
    }
  }

  function clearSnapshot() {
    $('snapshot').hidden = true;
    $('snapshot').removeAttribute('src');
    $('snapshot-placeholder').hidden = false;
    if (state.snapshotURL) URL.revokeObjectURL(state.snapshotURL);
    state.snapshotURL = null;
    $('snapshot-caption').textContent = 'Snapshot capture time has not been verified.';
  }

  function clearMetrics() {
    $('camera-fps').textContent = '—';
    $('fps-detail').textContent = 'Waiting for camera telemetry';
    $('freshness').textContent = 'Unknown';
    $('freshness').className = 'metric-value metric-value-text';
    $('freshness-detail').textContent = 'No freshness claim is available';
    $('lpr-status').textContent = '—';
  }

  function clearAnswer() {
    $('answer-content').hidden = true;
    $('answer-empty').hidden = false;
    $('response-mode').textContent = 'Ready when you are';
    for (const id of ['asked-question', 'answer', 'response-scope', 'coverage', 'limitations', 'events', 'request-reference']) $(id).replaceChildren();
  }

  function resetOperations(available) {
    busy($('refresh-live'), false, '↻ Refresh status');
    busy($('load-snapshot'), false, 'Load snapshot ↗');
    busy($('ask'), false, 'Retrieve evidence →');
    for (const id of ['refresh-live', 'load-snapshot', 'ask']) $(id).disabled = !available;
  }

  function disconnect() {
    state.generation += 1;
    for (const controller of state.controllers) controller.abort();
    state.key = null;
    state.cameras = [];
    state.selected = '';
    $('access-key').value = '';
    $('connection-card').hidden = false;
    $('disconnect').hidden = true;
    $('connection-state').className = 'connection-state';
    $('connection-state').replaceChildren(node('span', '', 'status-dot'), document.createTextNode('Disconnected'));
    $('camera').replaceChildren(node('option', 'Connect to choose a camera'));
    $('camera').disabled = true;
    $('camera-list').replaceChildren(node('p', 'Connect to load your camera catalog.', 'sidebar-empty'));
    $('camera-count').textContent = '0';
    $('aliases').textContent = '—';
    $('query-controls').disabled = true;
    resetOperations(false);
    clearSnapshot();
    clearMetrics();
    clearAnswer();
    alertMessage('');
  }

  function renderCatalog(cameras) {
    state.cameras = safeArray(cameras).filter(camera => camera && typeof camera.id === 'string');
    $('camera').replaceChildren();
    $('camera-list').replaceChildren();
    $('camera-count').textContent = state.cameras.length;
    for (const camera of state.cameras) {
      const option = node('option', camera.name || camera.id);
      option.value = camera.id;
      option.disabled = camera.enabled === false;
      $('camera').append(option);
      const button = node('button', null, 'camera-nav');
      button.type = 'button';
      button.disabled = camera.enabled === false;
      button.dataset.camera = camera.id;
      const labels = node('span');
      labels.append(node('span', camera.name || camera.id, 'camera-nav-name'), node('span', camera.enabled === false ? `${camera.id} · disabled` : camera.id, 'camera-nav-id'));
      button.append(node('span', '', 'camera-nav-indicator'), labels);
      button.addEventListener('click', () => selectCamera(camera.id));
      $('camera-list').append(button);
    }
    $('camera').disabled = !state.cameras.some(camera => camera.enabled !== false);
    if (!state.cameras.length) $('camera-list').append(node('p', 'No cameras were returned by the service.', 'sidebar-empty'));
  }

  async function connect(event) {
    event.preventDefault();
    const key = $('access-key').value.trim();
    if (!key) { alertMessage('Enter your access key to connect.'); return; }
    alertMessage('');
    busy($('connect'), true, 'Connecting…');
    $('access-key').disabled = true;
    try {
      const catalog = await request('/v1/cameras', {}, key);
      state.key = key;
      $('access-key').value = '';
      $('connection-card').hidden = true;
      $('disconnect').hidden = false;
      $('connection-state').className = 'connection-state connected';
      $('connection-state').replaceChildren(node('span', '', 'status-dot'), document.createTextNode('Local connection'));
      renderCatalog(catalog.cameras);
      const first = state.cameras.find(camera => camera.enabled !== false);
      if (first) await selectCamera(first.id);
      else alertMessage('Connected, but there are no enabled cameras to inspect.');
    } catch (error) {
      alertMessage(error.message);
    } finally {
      busy($('connect'), false, 'Connect →');
      $('access-key').disabled = false;
    }
  }

  async function selectCamera(id) {
    if (!state.key || !state.cameras.some(camera => camera.id === id && camera.enabled !== false)) return;
    state.generation += 1;
    for (const controller of state.controllers) controller.abort();
    state.selected = id;
    $('camera').value = id;
    for (const button of $('camera-list').children) button.setAttribute('aria-current', String(button.dataset.camera === id));
    const camera = state.cameras.find(value => value.id === id);
    $('aliases').textContent = safeArray(camera.aliases).filter(alias => typeof alias === 'string').join(' · ') || 'No additional aliases';
    $('query-controls').disabled = false;
    resetOperations(true);
    clearSnapshot();
    clearMetrics();
    clearAnswer();
    alertMessage('');
    await refreshLive();
  }

  function renderTelemetry(evidence) {
    const telemetry = evidence.telemetry || {};
    $('camera-fps').textContent = decimal(telemetry.camera_fps);
    $('fps-detail').textContent = `Processed ${decimal(telemetry.process_fps)} FPS · skipped ${decimal(telemetry.skipped_fps)} FPS`;
    const fresh = telemetry.healthy === true;
    $('freshness').textContent = fresh ? 'Fresh telemetry' : numeric(telemetry.stats_age_seconds) ? 'Stale or offline' : 'Unknown';
    $('freshness').className = `metric-value metric-value-text ${fresh ? 'tone-good' : 'tone-caution'}`;
    $('freshness-detail').textContent = numeric(telemetry.stats_age_seconds) ? `Stats ${telemetry.stats_age_seconds.toFixed(0)} seconds old · ${when(evidence.as_of)}` : 'The service could not establish telemetry freshness';
    $('lpr-status').textContent = evidence.camera_configuration?.lpr_enabled === true ? 'Enabled' : evidence.camera_configuration?.lpr_enabled === false ? 'Disabled' : 'Unknown';
  }

  async function refreshLive() {
    if (!state.selected || !state.key) return;
    const generation = state.generation;
    busy($('refresh-live'), true, 'Refreshing…');
    try {
      const evidence = await request(`/v1/live?${new URLSearchParams({ camera: state.selected })}`);
      if (generation === state.generation) renderTelemetry(evidence);
    } catch (error) { if (generation === state.generation) alertMessage(error.message); }
    finally { if (generation === state.generation) busy($('refresh-live'), false, '↻ Refresh status'); }
  }

  async function loadSnapshot() {
    if (!state.selected || !state.key) return;
    const generation = state.generation;
    busy($('load-snapshot'), true, 'Loading…');
    try {
      const image = await request(`/v1/snapshot?${new URLSearchParams({ camera: state.selected })}`, {}, state.key, true);
      if (generation !== state.generation) return;
      clearSnapshot();
      state.snapshotURL = URL.createObjectURL(image);
      $('snapshot').src = state.snapshotURL;
      $('snapshot').alt = `Snapshot from ${cameraName(state.selected)}; capture time is unverified`;
      $('snapshot').hidden = false;
      $('snapshot-placeholder').hidden = true;
      $('snapshot-caption').textContent = `Fetched ${when(new Date().toISOString())}. Capture time is unverified; an offline preview may be stale.`;
    } catch (error) { if (generation === state.generation) alertMessage(error.message); }
    finally { if (generation === state.generation) busy($('load-snapshot'), false, 'Load snapshot ↗'); }
  }

  function localField(date) {
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  function resetWindow() {
    const end = new Date();
    $('window-start').value = localField(new Date(end.getTime() - 30 * 60000));
    $('window-end').value = localField(end);
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'browser local time';
    $('timezone-note').textContent = `Times use ${zone}. Recaps use this explicit window, up to 48 hours; other answers may use live telemetry.`;
  }

  function windowValues() {
    const start = new Date($('window-start').value);
    const end = new Date($('window-end').value);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) throw new Error('Choose a start and end time.');
    if (end <= start || end - start > 48 * 3600000 || end.getTime() > Date.now() + 5000) throw new Error('Choose a completed window of at most 48 hours, with the end after the start.');
    return { start: start.toISOString(), end: end.toISOString() };
  }

  function renderCoverage(coverage) {
    $('coverage').replaceChildren();
    const entries = coverage && typeof coverage === 'object' ? Object.entries(coverage) : [];
    $('coverage').hidden = !entries.length;
    if (!entries.length) return;
    $('coverage').append(node('h3', 'Recording metadata coverage', 'coverage-heading'));
    for (const [camera, detail] of entries) {
      const item = detail || {};
      const row = node('div', null, `coverage-row ${item.complete ? '' : 'incomplete'}`);
      const bar = node('progress');
      bar.max = 1;
      if (numeric(item.fraction)) bar.value = Math.max(0, Math.min(1, item.fraction));
      else bar.value = 0;
      bar.setAttribute('aria-label', `Recording metadata coverage for ${cameraName(camera)}`);
      row.append(node('p', cameraName(camera)), bar, node('p', numeric(item.fraction) ? `${Math.round(item.fraction * 100)}% · ${item.complete ? 'complete' : 'gaps'}` : 'Unverified'));
      $('coverage').append(row);
    }
    $('coverage').append(node('p', 'Coverage reflects recording database intervals, not verified media integrity.', 'coverage-note'));
  }

  function eventCard(event) {
    const card = node('article', null, 'event-card');
    const top = node('div', null, 'event-top');
    top.append(node('h4', `Detector label: ${text(event.label)}`), node('span', `${score(event.top_score)} confidence`, 'event-score'));
    card.append(top, node('p', `${cameraName(event.camera)} · ${text(event.id)} · ${when(event.start_time)}`, 'citation'));
    card.append(node('p', event.end_time ? `Record ended: ${when(event.end_time)}` : 'Record remains open; current presence is not established.', 'event-detail'));
    if (safeArray(event.zones).length) card.append(node('p', `Zones: ${event.zones.map(text).join(', ')}`, 'event-detail'));
    if (event.plate_reading && typeof event.plate_reading === 'object') {
      const plate = node('p', `OCR: ${text(event.plate_reading.text)} · ${score(event.plate_reading.score)}`, 'event-plate');
      plate.append(node('span', 'UNVERIFIED', 'unverified-tag'));
      card.append(plate);
    }
    if (event.description_proposal?.text) {
      const details = node('details');
      details.append(node('summary', 'Unverified description proposal'), node('p', event.description_proposal.text));
      card.append(details);
    }
    return card;
  }

  function renderResponse(response, question) {
    const evidence = response.evidence || {};
    $('answer-empty').hidden = true;
    $('answer-content').hidden = false;
    $('asked-question').textContent = `Question: ${question}`;
    $('answer').textContent = text(response.answer);
    $('response-mode').textContent = response.mode === 'deterministic_evidence' ? 'Deterministic evidence' : 'Evidence response';
    $('response-scope').replaceChildren();
    const historic = Boolean(evidence.start && evidence.end);
    const cameras = historic ? safeArray(evidence.cameras) : [evidence.camera].filter(Boolean);
    $('response-scope').append(node('span', historic ? 'Scoped time-window recap' : 'Live telemetry & active records', 'scope-chip'));
    for (const camera of cameras) $('response-scope').append(node('span', cameraName(camera), 'scope-chip'));
    $('response-scope').append(node('span', historic ? `${when(evidence.start)} → ${when(evidence.end)}` : `As of ${when(evidence.as_of)}`, 'scope-chip'));
    const truncated = evidence.truncated === true || evidence.event_results_truncated === true;
    if (truncated) $('response-scope').append(node('span', 'Results capped · incomplete', 'scope-chip warning'));
    if (evidence.telemetry) renderTelemetry(evidence);
    renderCoverage(evidence.recording_coverage);
    $('limitations').replaceChildren();
    for (const limitation of safeArray(evidence.limitations)) $('limitations').append(node('p', limitation, 'limitation'));
    const events = safeArray(historic ? evidence.events : evidence.active_event_records);
    $('event-count').textContent = events.length;
    $('events').replaceChildren();
    for (const event of events) if (event && typeof event === 'object') $('events').append(eventCard(event));
    if (!events.length) $('events').append(node('p', 'No event records were returned. This does not establish that nothing happened.', 'empty-events'));
    $('request-reference').textContent = response.request_id ? `Request reference: ${response.request_id}` : '';
  }

  async function ask(event) {
    event.preventDefault();
    if (!state.key || !state.selected) { alertMessage('Connect and choose a camera first.'); return; }
    const question = $('question').value.trim();
    if (!question || question.length > 2000) { alertMessage('Enter a question of at most 2,000 characters.'); return; }
    let window;
    try { window = windowValues(); } catch (error) { alertMessage(error.message); return; }
    const generation = state.generation;
    alertMessage('');
    busy($('ask'), true, 'Retrieving…');
    try {
      const response = await request('/v1/query', { method: 'POST', body: JSON.stringify({ question, camera: state.selected, ...window }) });
      if (generation !== state.generation) return;
      renderResponse(response, question);
    } catch (error) { if (generation === state.generation) alertMessage(error.message); }
    finally { if (generation === state.generation) busy($('ask'), false, 'Retrieve evidence →'); }
  }

  $('connect-form').addEventListener('submit', connect);
  $('disconnect').addEventListener('click', disconnect);
  $('camera').addEventListener('change', () => selectCamera($('camera').value));
  $('refresh-live').addEventListener('click', refreshLive);
  $('load-snapshot').addEventListener('click', loadSnapshot);
  $('snapshot').addEventListener('error', () => { clearSnapshot(); alertMessage('The returned snapshot could not be displayed. Refresh the camera and try again.'); });
  $('query-form').addEventListener('submit', ask);
  $('last-30').addEventListener('click', resetWindow);
  for (const button of document.querySelectorAll('[data-preset]')) button.addEventListener('click', () => {
    $('question').value = presets[button.dataset.preset];
    for (const candidate of document.querySelectorAll('[data-preset]')) candidate.classList.toggle('active', candidate === button);
    $('question').focus();
  });
  $('question').addEventListener('input', () => { for (const button of document.querySelectorAll('[data-preset]')) button.classList.remove('active'); });
  window.addEventListener('pagehide', () => { if (state.snapshotURL) URL.revokeObjectURL(state.snapshotURL); state.key = null; });
  $('question').value = presets.live;
  resetWindow();
})();
