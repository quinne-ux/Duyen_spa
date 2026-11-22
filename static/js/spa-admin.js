'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const side = byId('adminSide');
  const overlay = byId('adminOverlay');
  byId('openAdminNav')?.addEventListener('click', () => { side?.classList.add('open'); overlay?.classList.add('visible'); });
  overlay?.addEventListener('click', () => { side?.classList.remove('open'); overlay.classList.remove('visible'); });

  document.querySelectorAll('[data-open-modal]').forEach(button => {
    button.addEventListener('click', () => byId(button.dataset.openModal)?.showModal());
  });
  document.querySelectorAll('[data-close-modal]').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog')?.close());
  });
  document.querySelectorAll('dialog.adm-dialog').forEach(dialog => {
    dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
  });
  document.querySelectorAll('[data-open-arrival]').forEach(button => {
    button.addEventListener('click', () => {
      const form = byId('arrivalForm');
      const input = byId('actualArrivals');
      if (!form || !input) return;
      form.action = button.dataset.openArrival;
      const max = Math.max(1, Number(button.dataset.size) || 1);
      input.max = String(max);
      input.value = String(max);
      byId('arrivalInfo').textContent = `Khách: ${button.dataset.name} · SĐT: ${button.dataset.phone} · Đã đặt: ${max} người`;
      byId('confirmArrival')?.showModal();
    });
  });
  document.querySelectorAll('[data-switch-view]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-switch-view]').forEach(b => b.classList.remove('active'));
      button.classList.add('active');
      if (byId('bookingList')) byId('bookingList').style.display = button.dataset.switchView === 'bookingList' ? '' : 'none';
      if (byId('slotList')) byId('slotList').style.display = button.dataset.switchView === 'slotList' ? '' : 'none';
    });
  });
})();
