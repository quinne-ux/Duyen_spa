'use strict';
(() => {
  const list = document.getElementById('staffList');
  const slots = document.getElementById('staffSlots');
  document.querySelectorAll('[data-staff-view]').forEach(button => {
    button.addEventListener('click', () => {
      const isList = button.dataset.staffView === 'list';
      list.hidden = !isList;
      slots.hidden = isList;
      document.querySelectorAll('[data-staff-view]').forEach(other => {
        const active = other === button;
        other.classList.toggle('active', active);
        other.setAttribute('aria-pressed', String(active));
      });
    });
  });

  const dialog = document.getElementById('staffArrivalDialog');
  const form = document.getElementById('staffArrivalForm');
  const amount = document.getElementById('staffActualArrivals');
  const info = document.getElementById('staffArrivalInfo');
  document.querySelectorAll('[data-staff-arrival-url]').forEach(button => {
    button.addEventListener('click', () => {
      const max = Math.max(1, Number(button.dataset.staffParty) || 1);
      form.action = button.dataset.staffArrivalUrl;
      amount.min = '1';
      amount.max = String(max);
      amount.value = String(max);
      info.textContent = `Khách: ${button.dataset.staffName} · SĐT: ${button.dataset.staffPhone} · Đã đặt: ${max} người`;
      dialog.showModal();
    });
  });
  document.getElementById('staffCloseDialog')?.addEventListener('click', () => dialog.close());
  document.getElementById('staffCancelDialog')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
})();
