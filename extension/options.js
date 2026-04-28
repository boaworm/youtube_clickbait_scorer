const DEFAULT_BACKEND_URL = 'http://localhost:4004';

document.addEventListener('DOMContentLoaded', () => {
  chrome.storage.sync.get(['backendUrl'], (result) => {
    document.getElementById('backendUrl').value = result.backendUrl || DEFAULT_BACKEND_URL;
  });

  document.getElementById('save').addEventListener('click', () => {
    const url = document.getElementById('backendUrl').value.trim().replace(/\/$/, '');
    chrome.storage.sync.set({ backendUrl: url }, () => {
      const status = document.getElementById('status');
      status.textContent = 'Saved.';
      setTimeout(() => { status.textContent = ''; }, 2000);
    });
  });
});
