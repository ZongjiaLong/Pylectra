// Pylectra docs — minimal client behavior
// Features:
//   1. ⌘/Ctrl+K → focus search
//   2. Floating action buttons (bottom-right):
//      - Back to previously read doc (sessionStorage, 1-deep)
//      - Bookmark current doc + open list panel (localStorage)

(function () {
  "use strict";

  const NS = "pylectra:";
  const KEY_CUR  = NS + "cur";
  const KEY_PREV = NS + "prev";
  const KEY_BMK  = NS + "bookmarks";

  // ---------- Storage helpers ----------
  function safeGet(storage, key) {
    try {
      const raw = storage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }
  function safeSet(storage, key, value) {
    try {
      storage.setItem(key, JSON.stringify(value));
    } catch (_) { /* quota or private mode — fail silently */ }
  }
  function safeRemove(storage, key) {
    try { storage.removeItem(key); } catch (_) {}
  }

  // ---------- History tracker ----------
  function recordHistory() {
    // Only track real content pages
    if (!document.querySelector("article.md-content__inner, article.md-content")) return;

    const here = { url: location.href, title: (document.title || location.href).trim() };
    const cur = safeGet(sessionStorage, KEY_CUR);

    if (cur && cur.url && cur.url !== here.url) {
      safeSet(sessionStorage, KEY_PREV, cur);
    }
    safeSet(sessionStorage, KEY_CUR, here);
  }

  function getPrev() {
    const prev = safeGet(sessionStorage, KEY_PREV);
    return prev && prev.url ? prev : null;
  }

  // ---------- Bookmarks ----------
  function loadBookmarks() {
    const arr = safeGet(localStorage, KEY_BMK);
    return Array.isArray(arr) ? arr : [];
  }
  function saveBookmarks(arr) {
    safeSet(localStorage, KEY_BMK, arr);
  }
  function isBookmarked(url) {
    return loadBookmarks().some((b) => b.url === url);
  }
  function toggleBookmark(url, title) {
    const arr = loadBookmarks();
    const idx = arr.findIndex((b) => b.url === url);
    if (idx >= 0) {
      arr.splice(idx, 1);
      saveBookmarks(arr);
      return false;
    }
    arr.unshift({ url, title: (title || url).trim(), addedAt: Date.now() });
    saveBookmarks(arr);
    return true;
  }
  function removeBookmark(url) {
    const arr = loadBookmarks().filter((b) => b.url !== url);
    saveBookmarks(arr);
  }

  // ---------- SVG icons ----------
  const ICON_BACK = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>';
  const ICON_STAR_OUTLINE = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
  const ICON_STAR_FILLED = '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
  const ICON_LIST = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>';
  const ICON_X = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';

  // ---------- FAB UI ----------
  function ensureFab() {
    let fab = document.querySelector("[data-pylectra-fab]");
    if (fab) return fab;

    fab = document.createElement("div");
    fab.className = "ply-fab";
    fab.setAttribute("data-pylectra-fab", "");
    fab.innerHTML = [
      '<button type="button" class="ply-fab__btn ply-fab__back" aria-label="Previous document">' + ICON_BACK + '</button>',
      '<button type="button" class="ply-fab__btn ply-fab__star" aria-label="Bookmark this page" aria-pressed="false">' + ICON_STAR_OUTLINE + '</button>',
      '<button type="button" class="ply-fab__btn ply-fab__list" aria-label="Show bookmarks" aria-expanded="false">' + ICON_LIST + '</button>',
      '<div class="ply-fab__panel" role="dialog" aria-label="Bookmarks" hidden>',
      '  <div class="ply-fab__panel-header">书签 · Bookmarks</div>',
      '  <ul class="ply-fab__list-ul"></ul>',
      '  <div class="ply-fab__empty" hidden>暂无书签 · No bookmarks yet</div>',
      '</div>'
    ].join("");
    document.body.appendChild(fab);

    bindFab(fab);
    return fab;
  }

  function bindFab(fab) {
    const backBtn = fab.querySelector(".ply-fab__back");
    const starBtn = fab.querySelector(".ply-fab__star");
    const listBtn = fab.querySelector(".ply-fab__list");
    const panel   = fab.querySelector(".ply-fab__panel");

    backBtn.addEventListener("click", function () {
      const prev = getPrev();
      if (prev && prev.url) location.assign(prev.url);
    });

    starBtn.addEventListener("click", function () {
      toggleBookmark(location.href, document.title);
      refreshUI();
    });

    listBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      togglePanel(panel, listBtn);
    });

    // Close panel on outside click
    document.addEventListener("click", function (e) {
      if (panel.hasAttribute("hidden")) return;
      if (fab.contains(e.target)) return;
      closePanel(panel, listBtn);
    });

    // Close panel on Esc
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hasAttribute("hidden")) {
        closePanel(panel, listBtn);
        listBtn.focus();
      }
    });
  }

  function togglePanel(panel, listBtn) {
    if (panel.hasAttribute("hidden")) {
      panel.removeAttribute("hidden");
      listBtn.setAttribute("aria-expanded", "true");
      // Force reflow then add anim class
      void panel.offsetWidth;
      panel.classList.add("is-open");
    } else {
      closePanel(panel, listBtn);
    }
  }
  function closePanel(panel, listBtn) {
    panel.classList.remove("is-open");
    panel.setAttribute("hidden", "");
    listBtn.setAttribute("aria-expanded", "false");
  }

  function renderBookmarkList(fab) {
    const ul = fab.querySelector(".ply-fab__list-ul");
    const empty = fab.querySelector(".ply-fab__empty");
    const items = loadBookmarks();

    ul.innerHTML = "";
    if (items.length === 0) {
      empty.removeAttribute("hidden");
      return;
    }
    empty.setAttribute("hidden", "");

    items.forEach(function (b) {
      const li = document.createElement("li");
      li.className = "ply-fab__item";

      const a = document.createElement("a");
      a.href = b.url;
      a.className = "ply-fab__item-link";
      a.textContent = b.title || b.url;
      a.title = b.title || b.url;

      const del = document.createElement("button");
      del.type = "button";
      del.className = "ply-fab__item-del";
      del.setAttribute("aria-label", "Remove bookmark");
      del.innerHTML = ICON_X;
      del.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        removeBookmark(b.url);
        refreshUI();
      });

      li.appendChild(a);
      li.appendChild(del);
      ul.appendChild(li);
    });
  }

  function refreshUI() {
    const fab = ensureFab();
    const backBtn = fab.querySelector(".ply-fab__back");
    const starBtn = fab.querySelector(".ply-fab__star");

    // Back button state
    const prev = getPrev();
    if (prev && prev.url && prev.url !== location.href) {
      backBtn.removeAttribute("disabled");
      backBtn.classList.remove("is-disabled");
      backBtn.title = "上一篇 · " + (prev.title || prev.url);
    } else {
      backBtn.setAttribute("disabled", "");
      backBtn.classList.add("is-disabled");
      backBtn.title = "无上一篇文档 · No previous doc";
    }

    // Star button state
    const marked = isBookmarked(location.href);
    starBtn.setAttribute("aria-pressed", marked ? "true" : "false");
    starBtn.classList.toggle("is-active", marked);
    starBtn.innerHTML = marked ? ICON_STAR_FILLED : ICON_STAR_OUTLINE;
    starBtn.title = marked ? "取消收藏 · Remove bookmark" : "收藏本页 · Bookmark this page";

    renderBookmarkList(fab);
  }

  // ---------- Search shortcut (existing behavior) ----------
  function focusSearch(e) {
    if ((e.metaKey || e.ctrlKey) && e.key && e.key.toLowerCase() === "k") {
      const toggle = document.querySelector('[data-md-toggle="search"]');
      const input = document.querySelector(".md-search__input");
      if (toggle && input) {
        e.preventDefault();
        toggle.checked = true;
        setTimeout(() => input.focus(), 30);
      }
    }
  }
  document.addEventListener("keydown", focusSearch);

  // ---------- Toast (Copy feedback) ----------
  function ensureToast() {
    let t = document.querySelector(".ply-toast");
    if (!t) {
      t = document.createElement("div");
      t.className = "ply-toast";
      t.setAttribute("role", "status");
      t.setAttribute("aria-live", "polite");
      document.body.appendChild(t);
    }
    return t;
  }
  function showToast(msg) {
    const t = ensureToast();
    t.textContent = msg;
    t.classList.remove("is-show");
    void t.offsetWidth;
    t.classList.add("is-show");
    clearTimeout(t._timer);
    t._timer = setTimeout(function () { t.classList.remove("is-show"); }, 1800);
  }
  document.addEventListener("click", function (e) {
    const btn = e.target && e.target.closest && e.target.closest('button.md-code__button[data-md-type="copy"]');
    if (btn) setTimeout(function () { showToast("已复制 · Copied to clipboard"); }, 30);
  });

  // ---------- Init ----------
  function init() {
    recordHistory();
    ensureFab();
    refreshUI();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // Forward-compat: re-run on Material instant navigation
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(function () { init(); });
  }
})();
