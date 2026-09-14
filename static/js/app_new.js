(function () {
  'use strict';

  const BASE_PATH = window.APP_BASE_PATH || '/sistema';
  const LOGOUT_URL = window.APP_LOGOUT_URL || (BASE_PATH + '/logout/');

  const STORAGE_THEME_KEY = 'horus-theme';
  const STORAGE_OP_MINI_KEY = 'horus-op-mini';
  const LEGACY_ICON_MAP = {
    'icon-pencil': 'bi bi-pencil-square',
    'icon-edit': 'bi bi-pencil-square',
    'icon-trash': 'bi bi-trash',
    'icon-refresh': 'bi bi-arrow-clockwise',
    'icon-list': 'bi bi-list-ul',
    'icon-print': 'bi bi-printer',
    'icon-plus': 'bi bi-plus-lg',
    'icon-camera': 'bi bi-camera',
    'icon-wrench': 'bi bi-wrench-adjustable',
    'icon-adjust': 'bi bi-sliders2',
    'icon-lock': 'bi bi-lock-fill'
  };

  const $id = function (id) {
    return document.getElementById(id);
  };

  const appRoot = $id('appRoot');
  const appSidebar = $id('appSidebar');
  const appLoader = $id('globalLoader');
  const appLoaderTitle = $id('globalLoaderTitle');
  const appLoaderMessage = $id('globalLoaderMessage');
  let modalCloseCallback = null;
  let modalAutoCloseTimer = null;
  let interfaceBlockCount = 0;

  function hasBootstrapModal() {
    return typeof window.bootstrap !== 'undefined' && !!window.bootstrap.Modal;
  }

  function normalizeLoaderState(payload) {
    const defaults = {
      title: 'Procesando solicitud',
      message: 'Espere un momento...'
    };

    if (!payload) {
      return defaults;
    }

    if (typeof payload === 'string') {
      return {
        title: payload.trim() || defaults.title,
        message: defaults.message
      };
    }

    if (typeof payload === 'object') {
      return {
        title: String(payload.title || defaults.title).trim() || defaults.title,
        message: String(payload.message || defaults.message).trim() || defaults.message
      };
    }

    return defaults;
  }

  function updateLoaderState(payload) {
    const state = normalizeLoaderState(payload);

    if (appLoaderTitle) {
      appLoaderTitle.textContent = state.title;
    }

    if (appLoaderMessage) {
      appLoaderMessage.textContent = state.message;
    }
  }

  function blockInterface(payload) {
    interfaceBlockCount += 1;

    if (!appLoader) {
      return;
    }

    updateLoaderState(payload);
    appLoader.classList.add('is-visible');
    appLoader.setAttribute('aria-hidden', 'false');
    appLoader.setAttribute('aria-busy', 'true');

    if (document.body) {
      document.body.classList.add('is-interface-blocked');
    }
  }

  function unblockInterface(force) {
    if (force === true || force === 'all') {
      interfaceBlockCount = 0;
    } else {
      interfaceBlockCount = Math.max(0, interfaceBlockCount - 1);
    }

    if (interfaceBlockCount > 0 || !appLoader) {
      return;
    }

    appLoader.classList.remove('is-visible');
    appLoader.setAttribute('aria-hidden', 'true');
    appLoader.setAttribute('aria-busy', 'false');

    if (document.body) {
      document.body.classList.remove('is-interface-blocked');
    }
  }

  window.bloqueointerface = blockInterface;
  window.desbloqueointerface = unblockInterface;
  window.showWaiting = function (title, message) {
    blockInterface({
      title: title || 'Procesando solicitud',
      message: message || 'Espere un momento...'
    });
  };
  window.hideWaiting = function () {
    unblockInterface('all');
  };

  function openReportWindow(url, width, height) {
    const popupWidth = Number(width || 800);
    const popupHeight = Number(height || 500);
    window.open(
      url,
      'horus_report',
      'height=' + popupHeight + ',width=' + popupWidth + ',noopener'
    );
  }

  function openWindow(verb, url, data, target) {
    const form = document.createElement('form');
    form.action = url;
    form.method = verb;
    form.target = target || '_self';
    form.style.display = 'none';

    if (data && typeof data === 'object') {
      Object.keys(data).forEach(function (key) {
        const input = document.createElement('textarea');
        input.name = key;
        input.value = typeof data[key] === 'object'
          ? JSON.stringify(data[key])
          : String(data[key]);
        form.appendChild(input);
      });
    }

    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  }

  window.openwindow_reporte = openReportWindow;
  window.openwindow = openWindow;

  function isMobile() {
    return window.innerWidth < 992;
  }

  function safeLocalStorageGet(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : value;
    } catch (e) {
      return fallback;
    }
  }

  function safeLocalStorageSet(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (e) {}
  }

  function escapeHtml(str) {
    return String(str || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function resolveAppUrl(url) {
    const rawUrl = String(url || '').trim();
    const normalizedBase = String(BASE_PATH || '').trim().replace(/\/+$/, '');

    if (!rawUrl || !normalizedBase) {
      return rawUrl;
    }

    if (/^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(rawUrl)) {
      return rawUrl;
    }

    if (rawUrl.startsWith('#') || rawUrl.toLowerCase().startsWith('javascript:')) {
      return rawUrl;
    }

    if (!rawUrl.startsWith('/')) {
      return rawUrl;
    }

    if (rawUrl === '/') {
      return normalizedBase + '/';
    }

    if (rawUrl === normalizedBase || rawUrl.startsWith(normalizedBase + '/')) {
      return rawUrl;
    }

    if (/^\/(admin|static|media|login|logout)\b/i.test(rawUrl)) {
      return rawUrl;
    }

    return normalizedBase + rawUrl;
  }

  function getPreferredTheme() {
    const saved = safeLocalStorageGet(STORAGE_THEME_KEY, null);
    if (saved === 'light' || saved === 'dark') {
      return saved;
    }

    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }

    return 'light';
  }

  function updateThemeButton(theme) {
    const btn = $id('themeToggle');
    const text = $id('themeToggleText');
    if (!btn) return;

    const icon = btn.querySelector('i');

    if (theme === 'dark') {
      if (text) text.textContent = 'Modo claro';
      if (icon) icon.className = 'fa-solid fa-sun me-2';
      btn.setAttribute('title', 'Cambiar a modo claro');
      btn.setAttribute('aria-label', 'Cambiar a modo claro');
    } else {
      if (text) text.textContent = 'Modo oscuro';
      if (icon) icon.className = 'fa-solid fa-moon me-2';
      btn.setAttribute('title', 'Cambiar a modo oscuro');
      btn.setAttribute('aria-label', 'Cambiar a modo oscuro');
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    safeLocalStorageSet(STORAGE_THEME_KEY, theme);
    updateThemeButton(theme);
  }

  function initTheme() {
    const themeToggle = $id('themeToggle');
    applyTheme(getPreferredTheme());

    if (themeToggle) {
      themeToggle.addEventListener('click', function () {
        const current = document.documentElement.getAttribute('data-bs-theme') || 'light';
        applyTheme(current === 'dark' ? 'light' : 'dark');
      });
    }
  }

  function initClock() {
    const clock = $id('clock');
    if (!clock || !window.__SERVER_DATE__) return;

    let serverDate = new Date(window.__SERVER_DATE__);

    function pad(n) {
      return String(n).padStart(2, '0');
    }

    function renderClock() {
      if (!(serverDate instanceof Date) || isNaN(serverDate.getTime())) {
        clock.textContent = '--:--';
        return;
      }

      clock.textContent =
        pad(serverDate.getHours()) + ':' +
        pad(serverDate.getMinutes()) + ':' +
        pad(serverDate.getSeconds());

      serverDate = new Date(serverDate.getTime() + 1000);
    }

    renderClock();
    setInterval(renderClock, 1000);
  }

  function openSidebar() {
    if (appSidebar) appSidebar.classList.add('open');
    document.body.classList.add('sidebar-is-open');
  }

  function closeSidebar() {
    if (appSidebar) appSidebar.classList.remove('open');
    document.body.classList.remove('sidebar-is-open');
  }

  function initSidebarMobile() {
    const sidebarOpen = $id('sidebarOpen');
    const sidebarClose = $id('sidebarClose');

    if (sidebarOpen) {
      sidebarOpen.addEventListener('click', openSidebar);
    }

    if (sidebarClose) {
      sidebarClose.addEventListener('click', closeSidebar);
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeSidebar();
      }
    });

    document.addEventListener('click', function (e) {
      if (!isMobile()) return;
      if (!appSidebar || !appSidebar.classList.contains('open')) return;

      const clickedInsideSidebar = e.target.closest('#appSidebar');
      const clickedSidebarOpen = e.target.closest('#sidebarOpen');

      if (!clickedInsideSidebar && !clickedSidebarOpen) {
        closeSidebar();
      }
    });

    window.addEventListener('resize', function () {
      if (!isMobile()) {
        closeSidebar();
      }
    });
  }

  function setOpMini(enabled) {
    if (!appRoot) return;

    appRoot.classList.toggle('op-mini', !!enabled);
    safeLocalStorageSet(STORAGE_OP_MINI_KEY, enabled ? '1' : '0');

    const icon = $id('opToggleIcon');
    const btn = $id('opToggle');

    if (icon) {
      icon.className = enabled
        ? 'fa-solid fa-angles-right'
        : 'fa-solid fa-angles-left';
    }

    if (btn) {
      const label = enabled ? 'Expandir panel' : 'Contraer panel';
      btn.setAttribute('title', label);
      btn.setAttribute('aria-label', label);
    }
  }

  function initOpMini() {
    const opToggle = $id('opToggle');
    if (!opToggle || !appRoot) return;

    const saved = safeLocalStorageGet(STORAGE_OP_MINI_KEY, '0');
    setOpMini(saved === '1');

    opToggle.addEventListener('click', function () {
      const enabled = !appRoot.classList.contains('op-mini');
      setOpMini(enabled);
    });
  }

  function getCompactText(element) {
    return String((element && element.textContent) || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function normalizeLegacyIcon(icon) {
    if (!icon) return;

    const className = String(icon.className || '').toLowerCase();
    if (!className) return;

    const legacyKey = Object.keys(LEGACY_ICON_MAP).find(function (key) {
      return icon.classList.contains(key);
    });

    if (legacyKey) {
      icon.className = LEGACY_ICON_MAP[legacyKey];
      icon.setAttribute('aria-hidden', 'true');
      return;
    }

    if (/\bbi-[a-z0-9-]+\b/i.test(className) && !icon.classList.contains('bi')) {
      icon.classList.add('bi');
    }

    if (/\bfa-[a-z0-9-]+\b/i.test(className)) {
      const hasFaStyle =
        icon.classList.contains('fa-solid') ||
        icon.classList.contains('fa-regular') ||
        icon.classList.contains('fa-brands') ||
        icon.classList.contains('fa-light') ||
        icon.classList.contains('fa-thin') ||
        icon.classList.contains('fa-duotone') ||
        icon.classList.contains('fa');

      if (!hasFaStyle) {
        icon.classList.add('fa-solid');
      }
    }
  }

  function detectLegacyButtonRole(button) {
    if (!button) return null;

    const icon = button.querySelector('i');
    const iconClass = icon ? String(icon.className || '').toLowerCase() : '';
    const title = String(
      button.getAttribute('title') ||
      button.getAttribute('aria-label') ||
      ''
    ).trim().toLowerCase();
    const text = getCompactText(button).toLowerCase();
    const targetUrl = String(
      button.getAttribute('nhref') ||
      button.getAttribute('href') ||
      button.getAttribute('data-modal-url') ||
      ''
    ).trim().toLowerCase();

    const isDelete =
      iconClass.indexOf('icon-trash') >= 0 ||
      iconClass.indexOf('bi-trash') >= 0 ||
      iconClass.indexOf('fa-trash') >= 0 ||
      title.indexOf('eliminar') >= 0 ||
      text === 'eliminar' ||
      targetUrl.indexOf('action=del') >= 0 ||
      targetUrl.indexOf('action=delete') >= 0 ||
      targetUrl.indexOf('eliminar') >= 0 ||
      targetUrl.indexOf('delete') >= 0;

    const isEdit =
      iconClass.indexOf('icon-pencil') >= 0 ||
      iconClass.indexOf('icon-edit') >= 0 ||
      iconClass.indexOf('bi-pencil') >= 0 ||
      iconClass.indexOf('fa-pencil') >= 0 ||
      iconClass.indexOf('fa-pen') >= 0 ||
      title.indexOf('editar') >= 0 ||
      text === 'editar' ||
      targetUrl.indexOf('action=edit') >= 0 ||
      /(?:^|[/?&])edit[a-z]*=/.test(targetUrl);

    const isCreate =
      iconClass.indexOf('icon-plus') >= 0 ||
      iconClass.indexOf('bi-person-plus') >= 0 ||
      iconClass.indexOf('bi-plus') >= 0 ||
      iconClass.indexOf('fa-user-plus') >= 0 ||
      iconClass.indexOf('fa-plus') >= 0 ||
      title.indexOf('adicionar') >= 0 ||
      title.indexOf('agregar') >= 0 ||
      title.indexOf('nuevo') >= 0 ||
      text.indexOf('adicionar') === 0 ||
      text.indexOf('agregar') === 0 ||
      text.indexOf('nuevo') === 0 ||
      targetUrl.indexOf('action=add') >= 0 ||
      targetUrl.indexOf('/add') >= 0;

    if (isDelete) return 'delete';
    if (isEdit) return 'edit';
    if (isCreate) return 'create';
    return null;
  }

  function ensureButtonIcon(button) {
    let icon = button.querySelector('i');
    if (!icon) {
      icon = document.createElement('i');
      button.insertBefore(icon, button.firstChild);
    }
    return icon;
  }

  function normalizeLegacyButtonIcon(button, role) {
    if (!button || !role) return;

    const icon = ensureButtonIcon(button);
    icon.setAttribute('aria-hidden', 'true');

    if (role === 'create') {
      icon.className = 'bi bi-plus-lg';
      return;
    }

    if (role === 'edit') {
      icon.className = 'bi bi-pencil-square';
      return;
    }

    if (role === 'delete') {
      icon.className = 'bi bi-trash';
    }
  }

  function normalizeLegacyActionButtons(root) {
    const scope = root || document;
    scope.querySelectorAll('i').forEach(normalizeLegacyIcon);

    const buttons = scope.querySelectorAll('a.btn, button.btn');

    buttons.forEach(function (button) {
      const role = detectLegacyButtonRole(button);
      if (!role) return;

      button.classList.add('btn-unified');

      if (role === 'create') {
        button.classList.add('btn-create');
        button.classList.remove('btn-action', 'btn-action-edit', 'btn-action-delete', 'btn-action-icon-only');
        button.classList.remove('btn-success');
      } else {
        button.classList.remove('btn-create');
        button.classList.add('btn-action');
        button.classList.toggle('btn-action-edit', role === 'edit');
        button.classList.toggle('btn-action-delete', role === 'delete');
        button.classList.remove('btn-success', 'btn-danger');
      }

      if (!getCompactText(button)) {
        button.classList.add('btn-action-icon-only');
      } else if (role !== 'create') {
        button.classList.remove('btn-action-icon-only');
      }

      const cell = button.closest('td, th');
      if (cell) {
        cell.classList.add('actions-cell');
      }

      if (!button.getAttribute('aria-label')) {
        button.setAttribute(
          'aria-label',
          role === 'create' ? 'Adicionar' : (role === 'edit' ? 'Editar' : 'Eliminar')
        );
      }

      normalizeLegacyButtonIcon(button, role);
    });
  }

  function getMainModalElements() {
    return {
      modalEl: $id('formulariomodaldinamico'),
      dialogEl: $id('formulariomodalDialog'),
      bodyEl: $id('formulariomodaldinamicobody')
    };
  }

  function clearModalAutoCloseTimer() {
    if (!modalAutoCloseTimer) return;

    window.clearTimeout(modalAutoCloseTimer);
    modalAutoCloseTimer = null;
  }

  function clearModalCloseCallback() {
    modalCloseCallback = null;
    clearModalAutoCloseTimer();
  }

  function setModalCloseCallback(callback) {
    modalCloseCallback = typeof callback === 'function' ? callback : null;
  }

  function applyModalSize(root) {
    const elements = getMainModalElements();
    const dialogEl = elements.dialogEl;
    if (!dialogEl) return;

    dialogEl.classList.remove('modal-sm', 'modal-lg', 'modal-xl');
    dialogEl.style.maxWidth = '';

    const marker = root ? root.querySelector('#ajaxformwidth') : null;
    const sizeToken = marker
      ? getCompactText(marker).replace('ajaxformwidth_', '').trim().toLowerCase()
      : '';

    if (!sizeToken || sizeToken === 'lg') {
      dialogEl.classList.add('modal-lg');
      return;
    }

    if (sizeToken === 'sm') {
      dialogEl.classList.add('modal-sm');
      return;
    }

    if (sizeToken === 'md') {
      dialogEl.style.maxWidth = '640px';
      return;
    }

    if (sizeToken === 'xl') {
      dialogEl.classList.add('modal-xl');
      return;
    }

    if (/^\d+$/.test(sizeToken)) {
      dialogEl.style.maxWidth = sizeToken + 'px';
      return;
    }

    dialogEl.classList.add('modal-lg');
  }

  function activateInjectedScripts(container) {
    if (!container) return;

    const scripts = Array.from(container.querySelectorAll('script'));
    scripts.forEach(function (script) {
      const replacement = document.createElement('script');

      Array.from(script.attributes).forEach(function (attr) {
        replacement.setAttribute(attr.name, attr.value);
      });

      replacement.textContent = script.textContent || '';
      script.parentNode.replaceChild(replacement, script);
    });
  }

  function clearModalContent() {
    const elements = getMainModalElements();
    if (elements.bodyEl) {
      elements.bodyEl.innerHTML = '';
    }
    applyModalSize(null);
  }

  function closeActiveModal(callback) {
    const elements = getMainModalElements();
    const modalEl = elements.modalEl;

    if (typeof callback === 'function') {
      setModalCloseCallback(callback);
    }

    if (!modalEl || !hasBootstrapModal()) {
      const pendingCallback = modalCloseCallback;
      clearModalCloseCallback();
      clearModalContent();
      if (pendingCallback) {
        pendingCallback();
      }
      return;
    }

    const modal = window.bootstrap.Modal.getInstance(modalEl) || window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.hide();
  }

  function showModalHtml(html) {
    const elements = getMainModalElements();
    const body = elements.bodyEl;
    const modalEl = elements.modalEl;

    if (!body || !modalEl || !hasBootstrapModal()) return;

    clearModalAutoCloseTimer();
    body.innerHTML = html;
    normalizeLegacyActionButtons(body);
    applyModalSize(body);
    initTooltips();
    activateInjectedScripts(body);

    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();
  }

  function showModalLoading() {
    showModalHtml(
      '<div class="p-4 text-center">' +
        '<div class="spinner-border text-primary mb-3" role="status"></div>' +
        '<div class="small text-muted">Cargando...</div>' +
      '</div>'
    );
  }

  function showModalError(message) {
    showModalHtml(
      '<div class="p-4">' +
        '<div class="alert alert-danger mb-0">' +
          '<i class="fa-solid fa-triangle-exclamation me-2"></i>' + escapeHtml(message) +
        '</div>' +
      '</div>'
    );
  }

  function showMessageModal(options) {
    const settings = options || {};
    const title = escapeHtml(settings.title || 'Informacion');
    const message = String(settings.message || '');
    const autoCloseMs = Number(settings.autoCloseMs || 0);

    setModalCloseCallback(settings.onClose);

    showModalHtml(
      '<div class="modal-header">' +
        '<h5 class="modal-title mb-0">' + title + '</h5>' +
        '<button type="button" class="btn-close js-modal-close" aria-label="Cerrar"></button>' +
      '</div>' +
      '<div class="modal-body p-3">' +
        '<div class="alert alert-info mb-0 horus-modal-message">' + message + '</div>' +
      '</div>' +
      '<div class="modal-footer d-flex gap-2 justify-content-end">' +
        '<button type="button" class="btn btn-sm btn-unified btn-create" data-horus-message-ok="1">' +
          '<i class="bi bi-check2-circle"></i> Aceptar' +
        '</button>' +
      '</div>'
    );

    const elements = getMainModalElements();
    if (!elements.bodyEl) return;

    const okButton = elements.bodyEl.querySelector('[data-horus-message-ok]');
    if (okButton) {
      okButton.addEventListener('click', function () {
        closeActiveModal();
      });
    }

    if (autoCloseMs > 0) {
      modalAutoCloseTimer = window.setTimeout(function () {
        closeActiveModal();
      }, autoCloseMs);
    }
  }

  function showErrorMessage(title, message) {
    if (typeof window.NotificacionError === 'function') {
      window.NotificacionError(title || 'Opss..!!', message || 'Ocurrio un error.');
      return;
    }

    showMessageModal({
      title: title || 'Error',
      message: escapeHtml(message || 'Ocurrio un error.')
    });
  }

  function getReportFormatModalElements() {
    return {
      modalEl: $id('formatoreporte'),
      selectEl: $id('formatoreporte_formato'),
      runEl: $id('formatoreporte_run')
    };
  }

  function normalizeReportFormat(format) {
    const rawFormat = String(format || '').trim().toLowerCase();
    if (!rawFormat) {
      return '';
    }

    if (rawFormat === 'doc') {
      return 'docx';
    }

    if (rawFormat === 'xls') {
      return 'xlsx';
    }

    return rawFormat;
  }

  function getAvailableReportFormats(rawTypes) {
    const source = String(rawTypes || '').trim();
    const fallback = ['pdf', 'docx', 'xlsx', 'csv'];

    if (!source) {
      return fallback;
    }

    const uniqueFormats = [];
    source.split(',').forEach(function (token) {
      const format = normalizeReportFormat(token);
      if (!format || uniqueFormats.indexOf(format) >= 0) {
        return;
      }

      if (['pdf', 'docx', 'xlsx', 'csv'].indexOf(format) >= 0) {
        uniqueFormats.push(format);
      }
    });

    return uniqueFormats.length ? uniqueFormats : fallback;
  }

  function getReportFormatLabel(format) {
    if (format === 'pdf') {
      return 'PDF';
    }

    if (format === 'docx') {
      return 'Word';
    }

    if (format === 'xlsx') {
      return 'Excel';
    }

    if (format === 'csv') {
      return 'CSV';
    }

    return String(format || '').toUpperCase();
  }

  function resolveReportFileUrl(path) {
    const rawPath = String(path || '').trim();
    if (!rawPath) {
      return '';
    }

    if (/^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(rawPath)) {
      return rawPath;
    }

    if (rawPath.startsWith('/')) {
      return window.location.origin + rawPath;
    }

    return window.location.origin + '/' + rawPath.replace(/^\/+/, '');
  }

  function buildReportRequestUrl(baseUrl, reportFormat) {
    const resolvedUrl = resolveAppUrl(baseUrl);
    if (!resolvedUrl) {
      return '';
    }

    const url = new URL(resolvedUrl, window.location.origin);
    url.searchParams.set('rt', normalizeReportFormat(reportFormat) || 'pdf');
    return url.toString();
  }

  function runDirectReport(baseUrl, reportFormat) {
    const reportUrl = buildReportRequestUrl(baseUrl, reportFormat);
    if (!reportUrl) {
      showErrorMessage('Opss..!!', 'No se encontro la ruta del reporte.');
      return;
    }

    blockInterface({
      title: 'Generando reporte',
      message: 'Espere unos segundos por favor...'
    });

    fetch(reportUrl, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
      .then(function (res) {
        if (!res.ok) {
          throw new Error('HTTP_ERROR');
        }

        return res.text();
      })
      .then(function (payload) {
        let data = {};

        try {
          data = JSON.parse(payload);
        } catch (e) {
          throw new Error('INVALID_JSON');
        }

        unblockInterface('all');

        if (data.result === 'ok' && data.reportfile) {
          const reportFileUrl = resolveReportFileUrl(data.reportfile);
          if (normalizeReportFormat(reportFormat) === 'pdf') {
            openReportWindow(reportFileUrl, 800, 500);
          } else {
            window.location.href = reportFileUrl;
          }
          return;
        }

        showErrorMessage('Opss..!!', data.mensaje || 'Error al generar el reporte.');
      })
      .catch(function () {
        unblockInterface('all');
        showErrorMessage('!!!', 'Error de conexion');
      });
  }

  function openReportFormatSelector(baseUrl, formats) {
    const elements = getReportFormatModalElements();
    if (!elements.modalEl || !elements.selectEl || !elements.runEl || !hasBootstrapModal()) {
      runDirectReport(baseUrl, formats[0] || 'pdf');
      return;
    }

    elements.selectEl.innerHTML = '';
    formats.forEach(function (format) {
      const option = document.createElement('option');
      option.value = format;
      option.textContent = getReportFormatLabel(format);
      elements.selectEl.appendChild(option);
    });

    elements.runEl.setAttribute('data-report-url', baseUrl);
    const modal = window.bootstrap.Modal.getOrCreateInstance(elements.modalEl);
    modal.show();
  }

  function handleDirectReportTrigger(trigger) {
    if (!trigger) {
      return;
    }

    const baseUrl =
      trigger.getAttribute('nhref') ||
      trigger.getAttribute('data-report-url') ||
      trigger.getAttribute('href');

    if (!baseUrl || /^javascript:/i.test(baseUrl)) {
      showErrorMessage('Opss..!!', 'No se encontro la ruta del reporte.');
      return;
    }

    const formats = getAvailableReportFormats(trigger.getAttribute('tipos'));
    const triggerInsideOpenModal = !!trigger.closest('.modal.show');

    if (triggerInsideOpenModal && formats.length > 1) {
      if (formats.indexOf('pdf') >= 0) {
        runDirectReport(baseUrl, 'pdf');
        return;
      }

      runDirectReport(baseUrl, formats[0] || 'pdf');
      return;
    }

    if (formats.length > 1) {
      openReportFormatSelector(baseUrl, formats);
      return;
    }

    runDirectReport(baseUrl, formats[0] || 'pdf');
  }

  function loadModalUrl(url) {
    const resolvedUrl = resolveAppUrl(url);
    if (!resolvedUrl) return;

    clearModalCloseCallback();
    showModalLoading();

    fetch(resolvedUrl, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin'
    })
      .then(function (res) {
        if (!res.ok) {
          throw new Error('Error HTTP');
        }
        return res.text();
      })
      .then(function (html) {
        showModalHtml(html);
      })
      .catch(function () {
        showModalError('No se pudo cargar la ventana.');
      });
  }

  function initModalLifecycle() {
    const elements = getMainModalElements();
    if (!elements.modalEl || !hasBootstrapModal()) return;

    elements.modalEl.addEventListener('hidden.bs.modal', function () {
      clearModalContent();
      const pendingCallback = modalCloseCallback;
      clearModalCloseCallback();
      if (pendingCallback) {
        pendingCallback();
      }
    });

    window.horusCloseModal = closeActiveModal;
    window.horusLoadModalUrl = loadModalUrl;
    window.horusResolveAppUrl = resolveAppUrl;
    window.horusShowMessage = showMessageModal;
  }

  function initDynamicModals() {
    document.addEventListener('click', function (e) {
      const closeTrigger = e.target.closest('.js-modal-close');
      if (closeTrigger) {
        e.preventDefault();
        closeActiveModal();
        return;
      }

      const trigger = e.target.closest(
        '[data-modal-url], .formmodal[nhref], .confirmacionmodal[nhref], .eliminacionmodal[nhref]'
      );
      if (!trigger) return;

      e.preventDefault();

      const url =
        trigger.getAttribute('data-modal-url') ||
        trigger.getAttribute('nhref');

      if (!url) return;

      loadModalUrl(url);

      if (isMobile()) {
        closeSidebar();
      }
    });
  }

  function initDirectReports() {
    document.addEventListener('click', function (e) {
      const reportTrigger = e.target.closest('.reportedirecto');
      if (!reportTrigger) {
        return;
      }

      e.preventDefault();
      handleDirectReportTrigger(reportTrigger);
    });

    const elements = getReportFormatModalElements();
    if (elements.runEl) {
      elements.runEl.addEventListener('click', function () {
        const baseUrl = elements.runEl.getAttribute('data-report-url') || '';
        const selectedFormat = elements.selectEl ? elements.selectEl.value : 'pdf';

        if (elements.modalEl && hasBootstrapModal()) {
          const modal = window.bootstrap.Modal.getInstance(elements.modalEl) || window.bootstrap.Modal.getOrCreateInstance(elements.modalEl);
          modal.hide();
        }

        runDirectReport(baseUrl, selectedFormat || 'pdf');
      });
    }

    window.conectar_reportes_interface = function () {
      return true;
    };
  }

  function initLegacySearchModule() {
    const input = $id('searchmodule');
    if (!input) return;

    function applyFilter() {
      const value = (input.value || '').trim().toUpperCase();
      const modules = document.querySelectorAll('.module-icon[data-nombre]');

      modules.forEach(function (item) {
        const nombre = (item.getAttribute('data-nombre') || '').toUpperCase();
        item.style.display = (!value || nombre.includes(value)) ? '' : 'none';
      });
    }

    input.addEventListener('input', applyFilter);
    input.addEventListener('keyup', applyFilter);
  }

  function initAutoHideAlerts() {
    const central = $id('contenidocentral');
    if (!central) return;

    setTimeout(function () {
      const alerts = central.querySelectorAll('.alert');
      alerts.forEach(function (alertEl) {
        alertEl.style.transition = 'opacity .8s ease';
        alertEl.style.opacity = '0';
        setTimeout(function () {
          if (alertEl.parentNode) {
            alertEl.parentNode.removeChild(alertEl);
          }
        }, 850);
      });
    }, 34000);
  }

  function initActionButtonAutoClick() {
    const btn = $id('action-button');
    if (btn) {
      btn.click();
    }
  }

  function doLogout() {
    window.location.href = LOGOUT_URL;
  }

  function initLogout() {
    const btnLogout = $id('btnLogout');
    const btnLogoutSidebar = $id('btnLogoutSidebar');

    if (btnLogout) {
      btnLogout.addEventListener('click', doLogout);
    }

    if (btnLogoutSidebar) {
      btnLogoutSidebar.addEventListener('click', doLogout);
    }
  }

  function initTooltips() {
    if (typeof window.bootstrap === 'undefined' || !window.bootstrap.Tooltip) return;

    const items = document.querySelectorAll('[title], [data-bs-toggle="tooltip"]');
    items.forEach(function (el) {
      try {
        window.bootstrap.Tooltip.getOrCreateInstance(el);
      } catch (e) {}
    });
  }

  function initGenericUX() {
    document.addEventListener('click', function (e) {
      const link = e.target.closest('a[href]');
      if (!link) return;
      if (!isMobile()) return;

      const href = link.getAttribute('href') || '';
      const isHash = href.startsWith('#');
      const isJs = href.toLowerCase().startsWith('javascript:');
      const isModal =
        link.hasAttribute('data-modal-url') ||
        link.classList.contains('formmodal') ||
        link.classList.contains('confirmacionmodal') ||
        link.classList.contains('eliminacionmodal');
      const isBlank = link.getAttribute('target') === '_blank';

      if (!isHash && !isJs && !isModal && !isBlank) {
        closeSidebar();
      }
    });
  }

  // ---------------------------------------------------------------------
  // Avisos de la casa. El alert() del navegador dice "localhost dice" y corta
  // la pantalla; esto usa el mismo modal que el resto del sistema.
  // ---------------------------------------------------------------------
  const ICONOS_AVISO = {
    exito: {clase: 'aviso-exito', icono: 'bi-check-circle-fill'},
    error: {clase: 'aviso-error', icono: 'bi-exclamation-octagon-fill'},
    alerta: {clase: 'aviso-alerta', icono: 'bi-exclamation-triangle-fill'},
    pregunta: {clase: 'aviso-pregunta', icono: 'bi-question-circle-fill'},
    info: {clase: 'aviso-info', icono: 'bi-info-circle-fill'}
  };

  function mostrarAviso(opciones) {
    const modalEl = document.getElementById('avisoModal');
    const tituloEl = document.getElementById('avisoModalTitulo');
    const textoEl = document.getElementById('avisoModalTexto');
    const iconoEl = document.getElementById('avisoModalIcono');
    const okEl = document.getElementById('avisoModalOk');
    const cancelarEl = document.getElementById('avisoModalCancelar');

    // Sin modal (una pantalla suelta, un test) se cae al aviso del navegador.
    if (!modalEl || !hasBootstrapModal()) {
      if (opciones.pregunta) {
        return Promise.resolve(window.confirm(opciones.mensaje || ''));
      }
      window.alert(opciones.mensaje || '');
      return Promise.resolve(true);
    }

    const tipo = ICONOS_AVISO[opciones.tipo] || ICONOS_AVISO.info;
    iconoEl.className = 'aviso-icono ' + tipo.clase;
    iconoEl.innerHTML = '<i class="bi ' + tipo.icono + '"></i>';
    tituloEl.textContent = opciones.titulo || 'Aviso';
    textoEl.textContent = opciones.mensaje || '';

    okEl.textContent = opciones.ok || (opciones.pregunta ? 'Si, hacerlo' : 'Entendido');
    okEl.className = 'btn ' + (opciones.peligro ? 'btn-danger' : 'btn-joga');
    cancelarEl.classList.toggle('d-none', !opciones.pregunta);

    const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);

    return new Promise(function (resolve) {
      let respuesta = false;

      function alAceptar() {
        respuesta = true;
        modal.hide();
      }

      function alCerrar() {
        okEl.removeEventListener('click', alAceptar);
        modalEl.removeEventListener('hidden.bs.modal', alCerrar);
        resolve(respuesta);
      }

      okEl.addEventListener('click', alAceptar);
      modalEl.addEventListener('hidden.bs.modal', alCerrar);
      modal.show();
    });
  }

  window.NotificacionExito = function (titulo, mensaje) {
    return mostrarAviso({tipo: 'exito', titulo: titulo || 'Listo', mensaje: mensaje});
  };

  window.NotificacionError = function (titulo, mensaje) {
    return mostrarAviso({tipo: 'error', titulo: titulo || 'Opss..!!', mensaje: mensaje});
  };

  window.NotificacionAlerta = function (icono, titulo, mensaje) {
    // Lo llaman con el icono adelante desde los modales de siempre.
    const tipo = {success: 'exito', error: 'error', warning: 'alerta'}[icono] || 'info';
    return mostrarAviso({tipo: tipo, titulo: titulo, mensaje: mensaje});
  };

  window.Avisar = function (mensaje, titulo) {
    return mostrarAviso({tipo: 'alerta', titulo: titulo || 'Un momento', mensaje: mensaje});
  };

  window.Preguntar = function (mensaje, opciones) {
    opciones = opciones || {};
    return mostrarAviso({
      tipo: 'pregunta',
      pregunta: true,
      titulo: opciones.titulo || 'Confirma',
      mensaje: mensaje,
      ok: opciones.ok,
      peligro: opciones.peligro
    });
  };

  // Botones de un solo clic: mandan un action al modulo y recargan. Son para
  // lo que no necesita preguntar nada, como abrirle el siguiente mes a un
  // jugador (las fechas y el precio ya se saben).
  function initAccionesDirectas() {
    document.addEventListener('click', function (e) {
      const boton = e.target.closest('.accion-directa');
      if (!boton) return;

      e.preventDefault();
      if (boton.dataset.trabajando === '1') return;

      const url = boton.getAttribute('data-url');
      const accion = boton.getAttribute('data-accion');
      if (!url || !accion) return;

      const datos = new FormData();
      datos.append('action', accion);
      if (boton.getAttribute('data-id')) {
        datos.append('id', boton.getAttribute('data-id'));
      }

      const meta = document.querySelector('meta[name="csrf-token"]');
      const csrf = window.csrftoken || (meta ? meta.content : '');

      boton.dataset.trabajando = '1';
      boton.classList.add('disabled');

      fetch(url, {
        method: 'POST',
        body: datos,
        headers: Object.assign(
          {'X-Requested-With': 'XMLHttpRequest'},
          csrf ? {'X-CSRFToken': csrf} : {}
        ),
        credentials: 'same-origin'
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.result === 'ok') {
            window.location.reload();
            return;
          }
          boton.dataset.trabajando = '';
          boton.classList.remove('disabled');
          window.NotificacionError('No se pudo',
            (data && (data.mensaje || data.error)) || 'Intenta de nuevo.');
        })
        .catch(function () {
          boton.dataset.trabajando = '';
          boton.classList.remove('disabled');
          window.NotificacionError('Sin conexion', 'Revisa la senal y vuelve a intentar.');
        });
    });
  }

  function init() {
    initTheme();
    initClock();
    initSidebarMobile();
    initOpMini();
    initModalLifecycle();
    initDynamicModals();
    initDirectReports();
    initLegacySearchModule();
    initAutoHideAlerts();
    initActionButtonAutoClick();
    initLogout();
    normalizeLegacyActionButtons(document);
    initTooltips();
    initGenericUX();
    initAccionesDirectas();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
