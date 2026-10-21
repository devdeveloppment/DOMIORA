/*
 * Anti double soumission et état de chargement pour tous les formulaires POST.
 * - Ignoré si un gestionnaire a annulé l'envoi (fetch, Alpine @submit.prevent) ou si le formulaire porte data-no-guard.
 * - Les boutons sont réactivés si l'utilisateur revient sur la page (cache arrière du navigateur).
 */
(function () {
  "use strict";
  var LABEL = "Envoi en cours…";

  function buttonsOf(form) {
    var inside = Array.prototype.slice.call(form.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]'));
    var outside = form.id ? Array.prototype.slice.call(document.querySelectorAll('[form="' + form.id + '"][type="submit"]')) : [];
    return inside.concat(outside);
  }

  function lock(form, submitter) {
    form.dataset.submitting = "1";
    form.setAttribute("aria-busy", "true");
    buttonsOf(form).forEach(function (btn) {
      btn.dataset.guardDisabled = btn.disabled ? "keep" : "1";
      btn.disabled = true;
      if (btn === submitter && btn.tagName === "BUTTON" && !btn.dataset.guardHtml) {
        btn.dataset.guardHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> ' + (btn.dataset.loadingText || LABEL);
      }
    });
  }

  function unlockAll() {
    document.querySelectorAll('form[data-submitting="1"]').forEach(function (form) {
      delete form.dataset.submitting;
      form.removeAttribute("aria-busy");
      buttonsOf(form).forEach(function (btn) {
        if (btn.dataset.guardDisabled === "1") btn.disabled = false;
        delete btn.dataset.guardDisabled;
        if (btn.dataset.guardHtml) { btn.innerHTML = btn.dataset.guardHtml; delete btn.dataset.guardHtml; }
      });
    });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || (form.method || "").toLowerCase() !== "post" || "noGuard" in form.dataset) return;
    if (form.dataset.submitting === "1") { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    var submitter = event.submitter || null;
    // Le bouton cliqué doit être transmis (name/value) : on désactive juste après l'envoi.
    form.dataset.submitting = "1";
    setTimeout(function () {
      if (event.defaultPrevented || form.target === "_blank") { delete form.dataset.submitting; return; }
      lock(form, submitter);
    }, 0);
  });

  window.addEventListener("pageshow", function (event) { if (event.persisted) unlockAll(); });
})();
