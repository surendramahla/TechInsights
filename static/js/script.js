/* ═══════════════════════════════════════════════
   TechInsights — Main JavaScript
   ═══════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {

    // ────────────────────────────────────────────
    // 1. Dark Mode Toggle
    // ────────────────────────────────────────────
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon   = document.getElementById('theme-icon');
    const html        = document.documentElement;

    const savedTheme = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = html.getAttribute('data-theme');
            const next    = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
            updateThemeIcon(next);
        });
    }

    function updateThemeIcon(theme) {
        if (!themeIcon) return;
        themeIcon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }

    // ────────────────────────────────────────────
    // 2. Mobile Nav Toggle
    // ────────────────────────────────────────────
    const mobileToggle = document.getElementById('mobile-toggle');
    const navLinks     = document.getElementById('nav-links');

    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('open');
            const isOpen = navLinks.classList.contains('open');
            mobileToggle.setAttribute('aria-expanded', isOpen);
        });
        // Close on outside click
        document.addEventListener('click', e => {
            if (!mobileToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove('open');
            }
        });
    }

    // ────────────────────────────────────────────
    // 3. Avatar Dropdown
    // ────────────────────────────────────────────
    const avatarBtn    = document.getElementById('avatar-btn');
    const dropdownMenu = document.getElementById('dropdown-menu');

    if (avatarBtn && dropdownMenu) {
        avatarBtn.addEventListener('click', e => {
            e.stopPropagation();
            dropdownMenu.classList.toggle('open');
        });
        document.addEventListener('click', () => {
            dropdownMenu.classList.remove('open');
        });
    }

    // ────────────────────────────────────────────
    // 4. Toast Auto-dismiss
    // ────────────────────────────────────────────
    const toasts = document.querySelectorAll('.toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            toast.style.transition = 'opacity .5s, transform .5s';
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(120%)';
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    });

    // ────────────────────────────────────────────
    // 5. Navbar scroll shadow
    // ────────────────────────────────────────────
    const navbar = document.getElementById('main-navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            navbar.style.boxShadow = window.scrollY > 10
                ? '0 2px 20px rgba(0,0,0,.12)'
                : 'none';
        }, { passive: true });
    }

    // ────────────────────────────────────────────
    // 6. Smooth scroll for anchor links
    // ────────────────────────────────────────────
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', e => {
            const target = document.querySelector(anchor.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ────────────────────────────────────────────
    // 7. Dashboard stat counters (animated)
    // ────────────────────────────────────────────
    animateCounters();

    // ────────────────────────────────────────────
    // 8. Relative Time updates
    // ────────────────────────────────────────────
    updateRelativeTimes();
    setInterval(updateRelativeTimes, 60000);

}); // end DOMContentLoaded

// ────────────────────────────────────────────────
// Global helper — show toast programmatically
// ────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const iconMap = {
        success: 'fa-check-circle',
        danger:  'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info:    'fa-info-circle',
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-icon"><i class="fas ${iconMap[type] || iconMap.info}"></i></div>
        <div class="toast-body">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()" aria-label="Close">
            <i class="fas fa-times"></i>
        </button>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = 'opacity .5s, transform .5s';
        toast.style.opacity    = '0';
        toast.style.transform  = 'translateX(120%)';
        setTimeout(() => toast.remove(), 500);
    }, 4500);
}

// ────────────────────────────────────────────────
// Animate number counters (hero stats)
// ────────────────────────────────────────────────
function animateCounters() {
    const counters = [
        { el: document.getElementById('stat-posts'),  endpoint: '/api/stats', key: 'posts' },
        { el: document.getElementById('stat-users'),  endpoint: '/api/stats', key: 'users' },
        { el: document.getElementById('stat-views'),  endpoint: '/api/stats', key: 'views' },
    ];

    // Fetch once if any counter exists
    if (!counters.some(c => c.el)) return;

    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            const targets = { posts: data.posts, users: data.users, views: data.views };
            counters.forEach(({ el, key }) => {
                if (!el) return;
                countUp(el, targets[key] || 0);
            });
        })
        .catch(() => {
            counters.forEach(({ el }) => { if (el) el.textContent = '—'; });
        });
}

function countUp(el, target) {
    let current  = 0;
    const step   = Math.max(1, Math.ceil(target / 60));
    const timer  = setInterval(() => {
        current += step;
        if (current >= target) { current = target; clearInterval(timer); }
        el.textContent = current.toLocaleString();
    }, 20);
}

// ─── Follow / Unfollow buttons (Event Delegation - Global) ───
document.addEventListener('click', async (e) => {
    const followBtn = e.target.closest('.follow-btn');
    if (followBtn) {
        e.preventDefault();
        const userId = followBtn.dataset.userId;
        const isFollowing = followBtn.dataset.isFollowing === 'true';
        const url = isFollowing ? `/unfollow/${userId}` : `/follow/${userId}`;
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        
        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken }
            });
            const data = await res.json();
            if (res.ok) {
                // Update all follow buttons for this user on the page
                document.querySelectorAll(`.follow-btn[data-user-id="${userId}"]`).forEach(btn => {
                    const nextFollowing = !isFollowing;
                    btn.dataset.isFollowing = nextFollowing ? 'true' : 'false';
                    btn.textContent = nextFollowing ? 'Following' : 'Follow';
                    btn.classList.toggle('btn-primary', !nextFollowing);
                    btn.classList.toggle('btn-outline', nextFollowing);
                });
                
                // If we are on the public profile page, update the followers count
                const followersCountEl = document.getElementById('followers-count');
                if (followersCountEl) {
                    followersCountEl.textContent = data.followers_count;
                }
                
                showToast(data.status === 'followed' ? `Following ${data.username}!` : `Unfollowed ${data.username}.`, 'success');
            } else {
                showToast(data.error || 'Error updating follow status.', 'danger');
            }
        } catch (err) {
            showToast('Error updating follow status.', 'danger');
        }
    }
});

// ────────────────────────────────────────────────
// Global helper — Relative Time updates
// ────────────────────────────────────────────────
function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    
    // Check if timezone difference or latency causes "future" times
    if (diffMs < -2000) {
        return 'Just now';
    }
    
    const diffSec = Math.floor(Math.max(0, diffMs) / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) {
        return 'Just now';
    } else if (diffMin < 60) {
        return `${diffMin} min${diffMin > 1 ? 's' : ''} ago`;
    } else if (diffHour < 24) {
        return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
    } else if (diffDay === 1) {
        return 'Yesterday';
    } else if (diffDay < 7) {
        return `${diffDay} day${diffDay > 1 ? 's' : ''} ago`;
    } else {
        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
    }
}

function updateRelativeTimes() {
    const timeElements = document.querySelectorAll('.relative-time');
    timeElements.forEach(el => {
        const timestampStr = el.dataset.timestamp;
        if (!timestampStr) return;
        const date = new Date(timestampStr);
        if (isNaN(date.getTime())) return;
        el.textContent = formatRelativeTime(date);
    });
}

