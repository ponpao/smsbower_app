/* ============================================================
   TK Story Studio — application
   Plain ES5+/DOM, no build step: works from a static server and
   from file:// alike. Talks to the Anthropic Messages API over
   raw fetch (no bundler here) with streaming enabled.
   ============================================================ */
(function () {
  'use strict';

  const { STYLES, MODELS, I18N, MARK, buildPrompt, buildSystemPrompt } = window.TK;

  const API_URL = 'https://api.anthropic.com/v1/messages';
  const API_VERSION = '2023-06-01';

  const KEY = {
    apiKey:  'tk_story_api_key',
    model:   'tk_story_model',
    theme:   'tk_story_theme',
    lang:    'tk_story_lang',
    draft:   'tk_story_draft',
    cfg:     'tk_story_cfg',
    trim:    'tk_story_trim',
    history: 'tk_story_history'
  };

  const HISTORY_MAX = 25;

  /* ---------- tiny helpers ---------- */
  const $  = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));

  const store = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
      } catch (e) { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* quota / private mode */ }
    },
    del(key) { try { localStorage.removeItem(key); } catch (e) {} }
  };

  function debounce(fn, ms) {
    let t;
    return function () {
      const args = arguments;
      clearTimeout(t);
      t = setTimeout(() => fn.apply(null, args), ms);
    };
  }

  /* ---------- state ---------- */
  const state = {
    lang:   store.get(KEY.lang, 'km'),
    theme:  store.get(KEY.theme, 'system'),
    view:   'studio',
    styleId: 's1',
    ratio:  '9:16',
    mode:   'static',
    trimMode: 'sentence',
    generating: false,
    controller: null,
    lastFocus: null
  };

  const t = (key) => (I18N[state.lang] && I18N[state.lang][key]) || I18N.en[key] || key;

  /* ---------- elements ---------- */
  const el = {
    html: document.documentElement,
    progress: $('#progress'),
    tabbar: $('#tabbar'),
    connPill: $('#connPill'),
    connLabel: $('#connLabel'),
    langBtn: $('#langBtn'),
    themeBtn: $('#themeBtn'),
    settingsBtn: $('#settingsBtn'),

    storyRaw: $('#storyRaw'),
    sourceStats: $('#sourceStats'),
    generateBtn: $('#generateBtn'),
    stopBtn: $('#stopBtn'),
    genStatus: $('#genStatus'),
    genKbd: $('#genKbd'),

    titleOut: $('#titleOut'),
    captionOut: $('#captionOut'),
    fullText: $('#fullText'),
    articleStats: $('#articleStats'),
    toVisualsBtn: $('#toVisualsBtn'),

    trimLen: $('#trimLen'),
    trimRange: $('#trimRange'),
    trimModeSeg: $('#trimModeSeg'),
    trimmedOut: $('#trimmedOut'),
    trimStats: $('#trimStats'),

    styleGrid: $('#styleGrid'),
    styleCount: $('#styleCount'),
    modeSeg: $('#modeSeg'),
    ratioSeg: $('#ratioSeg'),
    promptOut: $('#promptOut'),
    downloadPromptBtn: $('#downloadPromptBtn'),

    historyList: $('#historyList'),
    historyEmpty: $('#historyEmpty'),
    clearHistoryBtn: $('#clearHistoryBtn'),

    scrim: $('#scrim'),
    drawer: $('#settingsPanel'),
    closeSettingsBtn: $('#closeSettingsBtn'),
    apiKeyInput: $('#apiKeyInput'),
    toggleKeyBtn: $('#toggleKeyBtn'),
    connectBtn: $('#connectBtn'),
    modelSelect: $('#modelSelect'),
    modelHint: $('#modelHint'),
    themeSeg: $('#themeSeg'),
    langSeg: $('#langSeg'),
    clearDataBtn: $('#clearDataBtn'),

    cfg: {
      paraMin: $('#paraMin'), paraMax: $('#paraMax'),
      wordMin: $('#wordMin'), titleWords: $('#titleWords')
    },

    toasts: $('#toasts')
  };

  /* ============================================================
     i18n
     ============================================================ */
  function applyLang(lang) {
    state.lang = lang;
    store.set(KEY.lang, lang);
    el.html.setAttribute('lang', lang);

    $$('[data-i18n]').forEach((node) => { node.textContent = t(node.dataset.i18n); });

    $$('[data-i18n-attr]').forEach((node) => {
      node.dataset.i18nAttr.split(',').forEach((pair) => {
        const parts = pair.split(':');
        if (parts.length === 2) node.setAttribute(parts[0].trim(), t(parts[1].trim()));
      });
    });

    el.langBtn.textContent = lang === 'en' ? 'ខ្មែរ' : 'EN';
    $$('#langSeg .seg__btn').forEach((b) => b.classList.toggle('is-active', b.dataset.langChoice === lang));

    renderStyleGrid();
    renderModelHint();
    renderStats();
    renderHistory();
    setConnection(el.connPill.dataset.status || 'idle');
  }

  /* ============================================================
     theme
     ============================================================ */
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  function resolveTheme(choice) {
    if (choice === 'system') return media && media.matches ? 'dark' : 'light';
    return choice;
  }

  function applyTheme(choice) {
    state.theme = choice;
    store.set(KEY.theme, choice);
    el.html.setAttribute('data-theme', resolveTheme(choice));
    $$('#themeSeg .seg__btn').forEach((b) => b.classList.toggle('is-active', b.dataset.themeChoice === choice));
  }

  if (media && media.addEventListener) {
    media.addEventListener('change', () => { if (state.theme === 'system') applyTheme('system'); });
  }

  /* ============================================================
     toasts
     ============================================================ */
  function toast(message, kind) {
    const node = document.createElement('div');
    node.className = 'toast' + (kind ? ' is-' + kind : '');
    node.textContent = message;
    el.toasts.appendChild(node);
    setTimeout(() => {
      node.classList.add('is-out');
      setTimeout(() => node.remove(), 220);
    }, 2600);
  }

  /* ============================================================
     text statistics (Khmer-aware word counting)
     ============================================================ */
  const segmenter = (function () {
    try {
      if (typeof Intl !== 'undefined' && Intl.Segmenter) {
        return new Intl.Segmenter(undefined, { granularity: 'word' });
      }
    } catch (e) {}
    return null;
  })();

  function countWords(text) {
    if (!text.trim()) return 0;
    if (segmenter) {
      let n = 0;
      for (const seg of segmenter.segment(text)) if (seg.isWordLike) n++;
      return n;
    }
    return text.trim().split(/\s+/).length;
  }

  function measure(text) {
    const words = countWords(text);
    return {
      chars: text.length,
      words: words,
      paras: text.trim() ? text.trim().split(/\n\s*\n/).length : 0,
      minutes: Math.max(1, Math.round(words / 200))
    };
  }

  function statsLine(target, text, opts) {
    const m = measure(text);
    const parts = [
      '<b>' + m.words.toLocaleString() + '</b> ' + t('stats.words'),
      '<b>' + m.chars.toLocaleString() + '</b> ' + t('stats.chars')
    ];
    if (opts && opts.paras) parts.push('<b>' + m.paras + '</b> ' + t('stats.paras'));
    if (opts && opts.read && m.words > 0) parts.push('<b>' + m.minutes + '</b> ' + t('stats.read'));
    target.innerHTML = parts.map((p) => '<span>' + p + '</span>').join('');
  }

  function renderStats() {
    statsLine(el.sourceStats, el.storyRaw.value, { paras: true });
    statsLine(el.articleStats, el.fullText.value, { paras: true, read: true });
    statsLine(el.trimStats, el.trimmedOut.value, {});
  }

  /* ============================================================
     views
     ============================================================ */
  function showView(name) {
    state.view = name;
    $$('.view').forEach((v) => { v.hidden = v.id !== 'view-' + name; v.classList.toggle('is-active', v.id === 'view-' + name); });
    $$('.tab').forEach((tab) => {
      const on = tab.dataset.view === name;
      tab.classList.toggle('is-active', on);
      if (on) tab.setAttribute('aria-current', 'page'); else tab.removeAttribute('aria-current');
    });
    if (name === 'library') renderHistory();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  el.tabbar.addEventListener('click', (ev) => {
    const tab = ev.target.closest('.tab');
    if (tab) showView(tab.dataset.view);
  });

  el.toVisualsBtn.addEventListener('click', () => {
    if (!el.fullText.value.trim()) { toast(t('msg.needArticle'), 'error'); return; }
    showView('visuals');
  });

  /* ============================================================
     settings drawer (with focus trap)
     ============================================================ */
  function openDrawer() {
    state.lastFocus = document.activeElement;
    el.scrim.hidden = false;
    el.drawer.hidden = false;
    document.body.style.overflow = 'hidden';
    el.apiKeyInput.focus();
    document.addEventListener('keydown', onDrawerKeydown, true);
  }

  function closeDrawer() {
    el.scrim.hidden = true;
    el.drawer.hidden = true;
    document.body.style.overflow = '';
    document.removeEventListener('keydown', onDrawerKeydown, true);
    if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus();
  }

  function onDrawerKeydown(ev) {
    if (ev.key === 'Escape') { ev.preventDefault(); closeDrawer(); return; }
    if (ev.key !== 'Tab') return;
    const focusables = $$('button, input, select, textarea, a[href]', el.drawer)
      .filter((n) => !n.disabled && n.offsetParent !== null);
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
    else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
  }

  el.settingsBtn.addEventListener('click', openDrawer);
  el.connPill.addEventListener('click', openDrawer);
  el.closeSettingsBtn.addEventListener('click', closeDrawer);
  el.scrim.addEventListener('click', closeDrawer);

  /* ============================================================
     connection status
     ============================================================ */
  function setConnection(status, message) {
    el.connPill.dataset.status = status;
    el.connPill.classList.remove('is-ok', 'is-error', 'is-busy');
    if (status === 'ok')    el.connPill.classList.add('is-ok');
    if (status === 'error') el.connPill.classList.add('is-error');
    if (status === 'busy')  el.connPill.classList.add('is-busy');
    el.connLabel.textContent = message || t('conn.' + status);
    el.connPill.title = message || t('conn.' + status);
  }

  function apiKey() { return el.apiKeyInput.value.trim(); }

  function headers() {
    return {
      'Content-Type': 'application/json',
      'x-api-key': apiKey(),
      'anthropic-version': API_VERSION,
      'anthropic-dangerous-direct-browser-access': 'true'
    };
  }

  /* Request options that depend on what the selected model supports. */
  function modelOptions(modelId) {
    const spec = MODELS[modelId] || {};
    const body = { max_tokens: spec.maxTokens || 16000 };
    if (spec.adaptiveThinking) {
      body.thinking = { type: 'adaptive' };
      body.output_config = { effort: spec.effort || 'medium' };
    }
    return body;
  }

  el.connectBtn.addEventListener('click', async () => {
    if (!apiKey()) { setConnection('error', t('msg.needKey')); toast(t('msg.needKey'), 'error'); return; }
    el.connectBtn.disabled = true;
    setConnection('busy');
    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify({
          model: el.modelSelect.value,
          max_tokens: 16,
          messages: [{ role: 'user', content: 'Reply with OK.' }]
        })
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error((data.error && data.error.message) || ('HTTP ' + res.status));
      setConnection('ok');
      toast(t('conn.ok'), 'ok');
    } catch (err) {
      setConnection('error', shortError(err));
      toast(shortError(err), 'error');
    } finally {
      el.connectBtn.disabled = false;
    }
  });

  function shortError(err) {
    const msg = (err && err.message) || String(err);
    if (!navigator.onLine) return t('msg.offline');
    return msg.length > 120 ? msg.slice(0, 117) + '…' : msg;
  }

  /* ============================================================
     streaming generation
     ============================================================ */
  async function* streamText(body, signal) {
    const res = await fetch(API_URL, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(Object.assign({ stream: true }, body)),
      signal: signal
    });

    if (!res.ok) {
      let message = 'HTTP ' + res.status;
      try {
        const data = await res.json();
        if (data && data.error && data.error.message) message = data.error.message;
      } catch (e) {}
      throw new Error(message);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;

        let event;
        try { event = JSON.parse(payload); } catch (e) { continue; }

        if (event.type === 'error') {
          throw new Error((event.error && event.error.message) || 'stream error');
        }
        if (event.type === 'content_block_delta' && event.delta && event.delta.type === 'text_delta') {
          yield { text: event.delta.text };
        }
        if (event.type === 'message_delta' && event.usage) {
          yield { usage: event.usage };
        }
      }
    }
  }

  /* Split the marker-delimited response, tolerating a partial stream. */
  function splitSections(raw) {
    const ti = raw.indexOf(MARK.title);
    const ci = raw.indexOf(MARK.caption);
    const ai = raw.indexOf(MARK.article);

    if (ti === -1) return { title: '', caption: '', article: raw.trim(), complete: false };

    const titleEnd   = ci !== -1 ? ci : raw.length;
    const captionEnd = ai !== -1 ? ai : raw.length;

    return {
      title:   raw.slice(ti + MARK.title.length, titleEnd).trim(),
      caption: ci === -1 ? '' : raw.slice(ci + MARK.caption.length, captionEnd).trim(),
      article: ai === -1 ? '' : raw.slice(ai + MARK.article.length).trim(),
      complete: ti !== -1 && ci !== -1 && ai !== -1
    };
  }

  function setGenerating(on) {
    state.generating = on;
    el.generateBtn.disabled = on;
    el.stopBtn.hidden = !on;
    el.progress.hidden = !on;
  }

  function readConfig() {
    const num = (input, fallback) => {
      const n = parseInt(input.value, 10);
      return isNaN(n) ? fallback : n;
    };
    return {
      paraMin: num(el.cfg.paraMin, 10),
      paraMax: num(el.cfg.paraMax, 20),
      wordMin: num(el.cfg.wordMin, 1000),
      titleWords: num(el.cfg.titleWords, 20)
    };
  }

  async function generate() {
    if (state.generating) return;

    const story = el.storyRaw.value.trim();
    if (!apiKey())  { toast(t('msg.needKey'), 'error');   openDrawer(); return; }
    if (!story)     { toast(t('msg.needStory'), 'error'); el.storyRaw.focus(); return; }

    const model = el.modelSelect.value;
    const controller = new AbortController();
    state.controller = controller;
    setGenerating(true);

    el.genStatus.className = 'status';
    el.genStatus.innerHTML = '<span class="spinner"></span>' + t('msg.generating');

    const started = Date.now();
    let raw = '';
    let usage = null;

    try {
      const body = Object.assign(modelOptions(model), {
        model: model,
        system: buildSystemPrompt(readConfig()),
        messages: [{ role: 'user', content: 'Text:\n' + story }]
      });

      for await (const part of streamText(body, controller.signal)) {
        if (part.usage) { usage = part.usage; continue; }
        raw += part.text;

        const parts = splitSections(raw);
        el.titleOut.value = parts.title;
        el.captionOut.value = parts.caption;
        if (parts.article) {
          el.fullText.value = parts.article;
          el.fullText.scrollTop = el.fullText.scrollHeight;
        }
        renderStats();
      }

      doTrim();
      saveDraft();
      pushHistory({ title: el.titleOut.value, caption: el.captionOut.value, article: el.fullText.value, source: story, model: model });

      const seconds = Math.round((Date.now() - started) / 1000);
      const bits = [t('msg.done'), seconds + ' ' + t('stats.elapsed')];
      if (usage && usage.output_tokens) bits.push(usage.output_tokens.toLocaleString() + ' ' + t('stats.tokens'));
      el.genStatus.className = 'status is-ok';
      el.genStatus.textContent = bits.join(' · ');
      setConnection('ok');
      toast(t('msg.done'), 'ok');
    } catch (err) {
      if (err && err.name === 'AbortError') {
        el.genStatus.className = 'status';
        el.genStatus.textContent = t('msg.stopped');
      } else {
        el.genStatus.className = 'status is-error';
        el.genStatus.textContent = shortError(err);
        setConnection('error', shortError(err));
        toast(shortError(err), 'error');
      }
    } finally {
      state.controller = null;
      setGenerating(false);
    }
  }

  el.generateBtn.addEventListener('click', generate);
  el.stopBtn.addEventListener('click', () => { if (state.controller) state.controller.abort(); });

  /* ============================================================
     trimming
     ============================================================ */
  const SENTENCE_END = /[.!?。！？…]|។/g;

  function trimText(source, limit, mode) {
    if (source.length <= limit) return source;
    let cut = source.slice(0, limit);

    if (mode === 'word') {
      const space = cut.search(/\s\S*$/);
      if (space > limit * 0.6) cut = cut.slice(0, space);
    } else if (mode === 'sentence') {
      let best = -1;
      let match;
      SENTENCE_END.lastIndex = 0;
      while ((match = SENTENCE_END.exec(cut)) !== null) best = match.index + match[0].length;
      if (best > limit * 0.5) cut = cut.slice(0, best);
      else {
        const space = cut.search(/\s\S*$/);
        if (space > limit * 0.6) cut = cut.slice(0, space);
      }
    }
    return cut.replace(/\s+$/, '') + '........]';
  }

  function doTrim() {
    const limit = Math.max(20, parseInt(el.trimLen.value, 10) || 550);
    el.trimmedOut.value = trimText(el.fullText.value, limit, state.trimMode);
    renderStats();
    renderPrompt();
  }

  function syncTrimInputs(value) {
    const v = Math.max(20, parseInt(value, 10) || 550);
    el.trimLen.value = v;
    el.trimRange.value = Math.min(parseInt(el.trimRange.max, 10), v);
    store.set(KEY.trim, { length: v, mode: state.trimMode });
    doTrim();
  }

  el.trimLen.addEventListener('input', () => syncTrimInputs(el.trimLen.value));
  el.trimRange.addEventListener('input', () => syncTrimInputs(el.trimRange.value));

  el.trimModeSeg.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.seg__btn');
    if (!btn) return;
    state.trimMode = btn.dataset.trim;
    $$('.seg__btn', el.trimModeSeg).forEach((b) => b.classList.toggle('is-active', b === btn));
    store.set(KEY.trim, { length: parseInt(el.trimLen.value, 10), mode: state.trimMode });
    doTrim();
  });

  /* ============================================================
     style gallery + prompt panel
     ============================================================ */
  function renderStyleGrid() {
    el.styleGrid.innerHTML = '';
    STYLES.forEach((style) => {
      const label = style[state.lang] || style.en;
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'style-card' + (style.id === state.styleId ? ' is-active' : '');
      card.setAttribute('role', 'radio');
      card.setAttribute('aria-checked', String(style.id === state.styleId));
      card.dataset.style = style.id;
      card.innerHTML =
        '<span class="thumb ' + style.thumb + '" aria-hidden="true"><i></i><i></i><i></i><i></i></span>' +
        '<strong></strong><small></small>';
      $('strong', card).textContent = label[0];
      $('small', card).textContent = label[1];
      el.styleGrid.appendChild(card);
    });
    el.styleCount.textContent = String(STYLES.length);
  }

  el.styleGrid.addEventListener('click', (ev) => {
    const card = ev.target.closest('.style-card');
    if (!card) return;
    state.styleId = card.dataset.style;
    if (state.styleId === 'thumb') setRatio('16:9');
    $$('.style-card', el.styleGrid).forEach((c) => {
      const on = c === card;
      c.classList.toggle('is-active', on);
      c.setAttribute('aria-checked', String(on));
    });
    renderPrompt();
    $('.card--prompt').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });

  function setRatio(ratio) {
    state.ratio = ratio;
    $$('.seg__btn', el.ratioSeg).forEach((b) => b.classList.toggle('is-active', b.dataset.ratio === ratio));
  }

  el.ratioSeg.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.seg__btn');
    if (!btn) return;
    setRatio(btn.dataset.ratio);
    renderPrompt();
  });

  el.modeSeg.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.seg__btn');
    if (!btn) return;
    state.mode = btn.dataset.mode;
    $$('.seg__btn', el.modeSeg).forEach((b) => b.classList.toggle('is-active', b === btn));
    renderPrompt();
  });

  function renderPrompt() {
    const text = el.trimmedOut.value.trim();
    if (!text) { el.promptOut.value = ''; return; }
    el.promptOut.value = buildPrompt({
      styleId: state.styleId,
      ratio: state.ratio,
      mode: state.mode,
      text: text,
      title: el.titleOut.value.trim()
    });
  }

  el.downloadPromptBtn.addEventListener('click', () => {
    const text = el.promptOut.value;
    if (!text) { toast(t('msg.empty'), 'error'); return; }
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'tk-prompt-' + state.styleId + '-' + state.ratio.replace(':', 'x') + '.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast(t('msg.downloaded'), 'ok');
  });

  /* ============================================================
     copy buttons
     ============================================================ */
  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:-1000px;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    if (!ok) throw new Error('copy failed');
  }

  document.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('[data-copy]');
    if (!btn) return;
    const source = document.getElementById(btn.dataset.copy);
    const text = source ? source.value : '';
    if (!text.trim()) { toast(t('msg.empty'), 'error'); return; }
    try {
      await copyText(text);
      const original = btn.textContent;
      btn.classList.add('is-done');
      btn.textContent = t('action.copied');
      setTimeout(() => { btn.classList.remove('is-done'); btn.textContent = original; }, 1400);
      toast(t('msg.copied'), 'ok');
    } catch (e) {
      toast(t('msg.copyFail'), 'error');
    }
  });

  /* ============================================================
     history
     ============================================================ */
  function pushHistory(entry) {
    if (!entry.article.trim()) return;
    const list = store.get(KEY.history, []);
    list.unshift({
      id: String(Date.now()),
      at: new Date().toISOString(),
      title: entry.title,
      caption: entry.caption,
      article: entry.article,
      source: entry.source,
      model: entry.model,
      words: countWords(entry.article)
    });
    store.set(KEY.history, list.slice(0, HISTORY_MAX));
    renderHistory();
  }

  function renderHistory() {
    const list = store.get(KEY.history, []);
    el.historyList.innerHTML = '';
    el.historyEmpty.hidden = list.length > 0;

    list.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'history__item';

      const main = document.createElement('div');
      main.className = 'history__main';

      const h = document.createElement('p');
      h.className = 'history__title';
      h.textContent = item.title || item.article.slice(0, 60) + '…';

      const meta = document.createElement('div');
      meta.className = 'history__meta';
      const when = new Date(item.at);
      meta.textContent = when.toLocaleString(state.lang === 'km' ? 'km-KH' : 'en-GB', {
        dateStyle: 'medium', timeStyle: 'short'
      }) + ' · ' + item.words.toLocaleString() + ' ' + t('stats.words') + ' · ' + item.model;

      main.appendChild(h);
      main.appendChild(meta);

      const restore = document.createElement('button');
      restore.className = 'btn btn--mini';
      restore.type = 'button';
      restore.textContent = t('action.restore');
      restore.addEventListener('click', () => {
        el.titleOut.value = item.title || '';
        el.captionOut.value = item.caption || '';
        el.fullText.value = item.article || '';
        el.storyRaw.value = item.source || el.storyRaw.value;
        doTrim();
        saveDraft();
        showView('studio');
        toast(t('library.restored'), 'ok');
      });

      const del = document.createElement('button');
      del.className = 'btn btn--mini btn--danger';
      del.type = 'button';
      del.textContent = t('action.delete');
      del.addEventListener('click', () => {
        store.set(KEY.history, store.get(KEY.history, []).filter((x) => x.id !== item.id));
        renderHistory();
      });

      li.appendChild(main);
      li.appendChild(restore);
      li.appendChild(del);
      el.historyList.appendChild(li);
    });
  }

  el.clearHistoryBtn.addEventListener('click', () => {
    store.set(KEY.history, []);
    renderHistory();
    toast(t('library.cleared'), 'ok');
  });

  /* ============================================================
     persistence
     ============================================================ */
  const saveDraft = debounce(() => {
    store.set(KEY.draft, {
      story: el.storyRaw.value,
      title: el.titleOut.value,
      caption: el.captionOut.value,
      article: el.fullText.value
    });
  }, 400);

  const saveConfig = debounce(() => store.set(KEY.cfg, readConfig()), 400);

  function restore() {
    const draft = store.get(KEY.draft, null);
    if (draft) {
      el.storyRaw.value = draft.story || '';
      el.titleOut.value = draft.title || '';
      el.captionOut.value = draft.caption || '';
      el.fullText.value = draft.article || '';
    }

    const cfg = store.get(KEY.cfg, null);
    if (cfg) {
      Object.keys(el.cfg).forEach((k) => { if (cfg[k] != null) el.cfg[k].value = cfg[k]; });
    }

    const trim = store.get(KEY.trim, null);
    if (trim) {
      if (trim.length) { el.trimLen.value = trim.length; el.trimRange.value = Math.min(2000, trim.length); }
      if (trim.mode) {
        state.trimMode = trim.mode;
        $$('.seg__btn', el.trimModeSeg).forEach((b) => b.classList.toggle('is-active', b.dataset.trim === trim.mode));
      }
    }

    const savedKey = store.get(KEY.apiKey, '');
    if (savedKey) el.apiKeyInput.value = savedKey;

    const savedModel = store.get(KEY.model, 'claude-opus-5');
    if (MODELS[savedModel]) el.modelSelect.value = savedModel;
  }

  [el.storyRaw, el.titleOut, el.captionOut].forEach((node) => {
    node.addEventListener('input', () => { saveDraft(); renderStats(); renderPrompt(); });
  });

  el.fullText.addEventListener('input', () => { saveDraft(); doTrim(); });

  Object.keys(el.cfg).forEach((k) => el.cfg[k].addEventListener('input', saveConfig));

  el.apiKeyInput.addEventListener('input', () => {
    store.set(KEY.apiKey, apiKey());
    setConnection('idle');
  });

  el.toggleKeyBtn.addEventListener('click', () => {
    const showing = el.apiKeyInput.type === 'text';
    el.apiKeyInput.type = showing ? 'password' : 'text';
    el.toggleKeyBtn.classList.toggle('is-done', !showing);
  });

  function renderModelHint() {
    const spec = MODELS[el.modelSelect.value];
    el.modelHint.textContent = spec ? spec.hint[state.lang] || spec.hint.en : '';
  }

  el.modelSelect.addEventListener('change', () => {
    store.set(KEY.model, el.modelSelect.value);
    renderModelHint();
    setConnection('idle');
  });

  el.clearDataBtn.addEventListener('click', () => {
    if (!window.confirm(t('settings.confirmClear'))) return;
    Object.keys(KEY).forEach((k) => store.del(KEY[k]));
    toast(t('settings.cleared'), 'ok');
    setTimeout(() => window.location.reload(), 500);
  });

  el.themeSeg.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.seg__btn');
    if (btn) applyTheme(btn.dataset.themeChoice);
  });

  el.langSeg.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.seg__btn');
    if (btn) applyLang(btn.dataset.langChoice);
  });

  el.langBtn.addEventListener('click', () => applyLang(state.lang === 'en' ? 'km' : 'en'));

  el.themeBtn.addEventListener('click', () => {
    applyTheme(resolveTheme(state.theme) === 'dark' ? 'light' : 'dark');
  });

  /* ============================================================
     keyboard shortcuts
     ============================================================ */
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  el.genKbd.textContent = isMac ? '⌘↵' : 'Ctrl+↵';

  document.addEventListener('keydown', (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === 'Enter') {
      ev.preventDefault();
      if (state.generating) { if (state.controller) state.controller.abort(); }
      else generate();
    }
    if (ev.key === 'Escape' && state.generating && state.controller) state.controller.abort();
  });

  window.addEventListener('beforeunload', (ev) => {
    if (state.generating) { ev.preventDefault(); ev.returnValue = ''; }
  });

  window.addEventListener('offline', () => setConnection('error', t('msg.offline')));

  /* ============================================================
     boot
     ============================================================ */
  restore();
  applyTheme(state.theme);
  applyLang(state.lang);
  setConnection('idle');
  doTrim();
  renderStats();

  /* Service worker: only meaningful over http(s); skipped on file:// */
  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('sw.js').catch(() => { /* offline support is optional */ });
    });
  }
})();
