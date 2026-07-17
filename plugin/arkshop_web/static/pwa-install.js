/**
 * ARKLAND Web Store — prompt de instalação PWA.
 * Chromium: beforeinstallprompt. iOS Safari: instruções manuais.
 */
(function () {
  "use strict";

  var deferredPrompt = null;
  var DISMISS_KEY = "arkland_pwa_install_dismissed_v1";

  function isStandalone() {
    try {
      if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
        return true;
      }
    } catch (_) {}
    return Boolean(window.navigator.standalone);
  }

  function isIos() {
    var ua = window.navigator.userAgent || "";
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  }

  function wasDismissed() {
    try {
      return localStorage.getItem(DISMISS_KEY) === "1";
    } catch (_) {
      return false;
    }
  }

  function setDismissed() {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch (_) {}
  }

  function qs(sel) {
    return document.querySelector(sel);
  }

  function show(el) {
    if (el) el.classList.remove("hidden");
  }

  function hide(el) {
    if (el) el.classList.add("hidden");
  }

  function refreshUi() {
    var installBtns = document.querySelectorAll("[data-pwa-install]");
    var iosHints = document.querySelectorAll("[data-pwa-ios-hint]");
    var installedHints = document.querySelectorAll("[data-pwa-installed]");

    if (isStandalone()) {
      installBtns.forEach(hide);
      iosHints.forEach(hide);
      installedHints.forEach(show);
      return;
    }

    installedHints.forEach(hide);

    if (deferredPrompt) {
      installBtns.forEach(show);
      iosHints.forEach(hide);
      return;
    }

    installBtns.forEach(hide);
    if (isIos() && !wasDismissed()) {
      iosHints.forEach(show);
    } else {
      iosHints.forEach(hide);
    }
  }

  async function triggerInstall(ev) {
    if (ev) ev.preventDefault();
    if (!deferredPrompt) return;
    var promptEvent = deferredPrompt;
    deferredPrompt = null;
    refreshUi();
    try {
      await promptEvent.prompt();
      await promptEvent.userChoice;
    } catch (_) {}
    refreshUi();
  }

  function dismissIos(ev) {
    if (ev) ev.preventDefault();
    setDismissed();
    refreshUi();
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(function () {});
    });
  }

  function bindButtons() {
    document.querySelectorAll("[data-pwa-install]").forEach(function (btn) {
      btn.addEventListener("click", triggerInstall);
    });
    document.querySelectorAll("[data-pwa-ios-dismiss]").forEach(function (btn) {
      btn.addEventListener("click", dismissIos);
    });
  }

  function init() {
    registerServiceWorker();
    bindButtons();

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      refreshUi();
    });

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      refreshUi();
    });

    refreshUi();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
