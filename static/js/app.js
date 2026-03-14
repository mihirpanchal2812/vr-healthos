/* ═══════════════════════════════════════════════════════════
   VR HealthOS — Frontend Logic
   ═══════════════════════════════════════════════════════════ */

// ── Modal System ─────────────────────────────────────────
function openModal(id) {
    document.getElementById(id).classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
    document.body.style.overflow = '';
}

// Close modal on overlay click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// Close modal on Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(m => {
            m.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
});

// ── Toast Notifications ──────────────────────────────────
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success'
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
    toast.innerHTML = `<span class="toast-icon">${icon}</span> ${message}`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ── Sidebar Mobile Toggle ────────────────────────────────
document.addEventListener('click', function(e) {
    const sidebar = document.getElementById('sidebar');
    if (sidebar && sidebar.classList.contains('open') && !e.target.closest('.sidebar') && !e.target.closest('.hamburger')) {
        sidebar.classList.remove('open');
    }
});

// ── Confirmation Dialog ──────────────────────────────────
function showConfirmDialog(title, message, onConfirm, confirmText = 'Delete', confirmClass = 'btn-danger') {
    // Remove any existing dialog
    const existing = document.getElementById('confirmDialogOverlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'confirmDialogOverlay';
    overlay.className = 'modal-overlay active';
    overlay.innerHTML = `
        <div class="modal" style="max-width:420px">
            <div class="modal-header">
                <h2>${title}</h2>
                <button class="modal-close" onclick="closeConfirmDialog()"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
            </div>
            <div class="modal-body">
                <p style="font-size:14px;color:var(--text-muted);margin-bottom:20px;line-height:1.6">${message}</p>
                <div style="display:flex;gap:8px;justify-content:flex-end">
                    <button class="btn btn-outline" onclick="closeConfirmDialog()">Cancel</button>
                    <button class="btn ${confirmClass}" id="confirmDialogBtn">${confirmText}</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    document.body.style.overflow = 'hidden';

    document.getElementById('confirmDialogBtn').addEventListener('click', function() {
        closeConfirmDialog();
        onConfirm();
    });

    // Close on overlay click
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) closeConfirmDialog();
    });
}

function closeConfirmDialog() {
    const overlay = document.getElementById('confirmDialogOverlay');
    if (overlay) {
        overlay.remove();
        // Only restore scroll if no other modal is open
        if (!document.querySelector('.modal-overlay.active')) {
            document.body.style.overflow = '';
        }
    }
}
