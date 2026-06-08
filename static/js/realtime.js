let socket = null;
if (typeof io !== 'undefined') {
    try {
        socket = io();
    } catch(err) {
        console.error("Socket.io connection error:", err);
    }
}

if (!socket) {
    console.warn("Socket.io library not loaded or server down. Realtime listeners disabled, using fallback UI.");
    socket = {
        on: function(event, callback) {
            console.log(`Mock socket.on(${event})`);
        },
        emit: function(event, data) {
            console.log(`Mock socket.emit(${event})`, data);
        }
    };
}

// ── Notifications ─────────────────────────────────────
const notifBtn = document.getElementById('notif-btn');
const notifMenu = document.getElementById('notif-menu');
const notifBadge = document.getElementById('notif-badge');
const notifList = document.getElementById('notif-list');

// Toggle Dropdown
notifBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    notifMenu.style.display = notifMenu.style.display === 'block' ? 'none' : 'block';
});
document.addEventListener('click', (e) => {
    if (!notifMenu.contains(e.target) && e.target !== notifBtn) {
        notifMenu.style.display = 'none';
    }
});

// Load Initial Notifications
async function loadNotifications() {
    try {
        const res = await fetch('/realtime/notifications');
        const data = await res.json();
        updateBadge(data.unread_count);
        renderNotifications(data.notifications);
    } catch(e) { console.error('Failed to load notifications'); }
}

function updateBadge(count) {
    if(count > 0) {
        notifBadge.style.display = 'inline-block';
        notifBadge.textContent = count;
    } else {
        notifBadge.style.display = 'none';
        notifBadge.textContent = '0';
    }
}

function renderNotifications(notifications) {
    notifList.innerHTML = '';
    if(notifications.length === 0) {
        notifList.innerHTML = '<div style="padding: 15px; text-align: center; color: var(--text-muted); font-size:14px;">No notifications yet.</div>';
        return;
    }
    
    notifications.forEach(n => {
        const item = document.createElement('a');
        item.href = n.link_url || '#';
        item.className = `dropdown-item notif-item ${n.is_read ? 'read' : 'unread'}`;
        item.style.cssText = `padding: 10px 15px; border-bottom: 1px solid var(--border-color); display: block; text-decoration: none; color: inherit; background: ${n.is_read ? 'transparent' : 'rgba(13, 110, 253, 0.05)'}`;
        item.innerHTML = `
            <div style="font-size:14px; margin-bottom:4px;">
                <i class="fas ${getIconForType(n.type)}" style="color: var(--primary-color); margin-right:8px;"></i>
                ${n.message}
            </div>
            <div style="font-size:11px; color:var(--text-muted);" class="relative-time" data-timestamp="${n.created_at}">${n.created_at}</div>
        `;
        item.addEventListener('click', (e) => {
            if(!n.is_read) markAsRead(n.id);
        });
        notifList.appendChild(item);
    });

    if (typeof updateRelativeTimes === 'function') {
        updateRelativeTimes();
    }
}

function getIconForType(type) {
    switch(type) {
        case 'like': return 'fa-heart text-danger';
        case 'comment': return 'fa-comment text-primary';
        case 'bookmark': return 'fa-bookmark text-success';
        case 'follow': return 'fa-user-plus text-info';
        default: return 'fa-bell';
    }
}

async function markAsRead(id) {
    await fetch(`/realtime/notifications/read/${id}`, { method: 'POST', headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content} });
    loadNotifications();
}

document.getElementById('mark-all-read').addEventListener('click', async (e) => {
    e.preventDefault();
    await fetch('/realtime/notifications/read_all', { method: 'POST', headers: {'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content} });
    loadNotifications();
});

// Socket Event Listeners
socket.on('connect', () => {
    console.log('Connected to realtime server');
    loadNotifications();
});

socket.on('new_notification', (data) => {
    showToast(data.message, 'info');
    loadNotifications();
});

// Initialize notifications on page load and setup fallback polling
document.addEventListener('DOMContentLoaded', () => {
    loadNotifications();
    
    // Polling fallback for notifications when socket is offline
    if (!socket || typeof socket.connected === 'undefined' || !socket.connected) {
        setInterval(loadNotifications, 30000);
    }
});


// ── Chat System ─────────────────────────────────────
const chatPopup = document.getElementById('chat-popup');
const chatList = document.getElementById('chat-conversations-list');
const chatWindow = document.getElementById('chat-window');
const chatMessages = document.getElementById('chat-messages-container');
const chatInput = document.getElementById('chat-input');
const chatSendBtn = document.getElementById('chat-send-btn');
const chatActiveUser = document.getElementById('chat-active-user');

let activeChatUserId = null;
let typingTimeout = null;
let chatPollInterval = null;

function toggleChatSidebar() {
    if(chatPopup.style.display === 'flex') {
        chatPopup.style.display = 'none';
        clearInterval(chatPollInterval);
    } else {
        chatPopup.style.display = 'flex';
        loadConversations();
    }
}

function closeChatWindow() {
    chatWindow.style.display = 'none';
    chatList.style.display = 'flex';
    activeChatUserId = null;
    clearInterval(chatPollInterval);
    loadConversations();
}

async function loadConversations() {
    chatWindow.style.display = 'none';
    chatList.style.display = 'flex';
    try {
        const res = await fetch('/realtime/chat/conversations');
        const data = await res.json();
        renderConversations(data.conversations);
    } catch(e) { console.error('Failed to load conversations', e); }
}

function renderConversations(convs) {
    chatList.innerHTML = '';
    if(convs.length === 0) {
        chatList.innerHTML = '<div style="padding:20px; text-align:center; color:var(--text-muted);">No messages yet.</div>';
        return;
    }
    convs.forEach(c => {
        const div = document.createElement('div');
        div.className = 'conv-item';
        // if c.other_avatar is a URL or local file
        const avatarSrc = c.other_avatar.startsWith('http') ? c.other_avatar : `/static/uploads/${c.other_avatar}`;
        div.innerHTML = `
            <img src="${avatarSrc}" class="conv-avatar">
            <div class="conv-info">
                <div class="conv-name">
                    ${c.other_username}
                    <span class="conv-time">${c.last_message_time}</span>
                </div>
                <div class="conv-last-msg">${c.last_message || ''}</div>
            </div>
        `;
        div.onclick = () => openChat(c.other_user_id, c.other_username);
        chatList.appendChild(div);
    });
}

async function openChat(userId, username) {
    activeChatUserId = userId;
    chatActiveUser.textContent = username;
    chatList.style.display = 'none';
    chatWindow.style.display = 'flex';
    chatMessages.innerHTML = '<div style="text-align:center; padding:10px;"><i class="fas fa-spinner fa-spin"></i></div>';
    
    try {
        const res = await fetch(`/realtime/chat/messages/${userId}`);
        const data = await res.json();
        renderMessages(data.messages);
    } catch(e) { console.error(e); }

    // Fallback polling: if socket is mock or disconnected, poll messages every 4 seconds
    clearInterval(chatPollInterval);
    if (!socket || typeof socket.connected === 'undefined' || !socket.connected) {
        chatPollInterval = setInterval(async () => {
            if (activeChatUserId === userId && chatWindow.style.display === 'flex') {
                try {
                    const res = await fetch(`/realtime/chat/messages/${userId}`);
                    const data = await res.json();
                    const currentCount = chatMessages.querySelectorAll('.chat-message').length;
                    if (data.messages.length !== currentCount) {
                        renderMessages(data.messages);
                    }
                } catch(e) { console.error('Failed to poll messages', e); }
            } else {
                clearInterval(chatPollInterval);
            }
        }, 4000);
    }
}

function renderMessages(messages) {
    chatMessages.innerHTML = '';
    messages.forEach(m => appendMessage(m));
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendMessage(m) {
    const div = document.createElement('div');
    const isSent = m.sender_id === currentUserId;
    div.className = `chat-message ${isSent ? 'sent' : 'received'}`;
    div.innerHTML = `${m.content} <span class="time">${m.timestamp}</span>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Send message
chatSendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if(e.key === 'Enter') sendMessage();
    
    // Typing indicator
    if(activeChatUserId && socket && typeof socket.connected !== 'undefined' && socket.connected) {
        socket.emit('typing', {receiver_id: activeChatUserId});
        clearTimeout(typingTimeout);
        typingTimeout = setTimeout(() => {
            socket.emit('stop_typing', {receiver_id: activeChatUserId});
        }, 1500);
    }
});

async function sendMessage() {
    const text = chatInput.value.trim();
    if(!text || !activeChatUserId) return;
    
    if (socket && typeof socket.connected !== 'undefined' && socket.connected) {
        socket.emit('send_message', {
            receiver_id: activeChatUserId,
            message: text
        });
    } else {
        // Fallback to HTTP POST
        try {
            const res = await fetch('/realtime/chat/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: JSON.stringify({
                    receiver_id: activeChatUserId,
                    message: text
                })
            });
            const data = await res.json();
            if (data.status === 'success') {
                appendMessage(data.message);
            } else {
                showToast('Failed to send message', 'danger');
            }
        } catch (err) {
            console.error('HTTP send message error:', err);
            showToast('Failed to send message', 'danger');
        }
    }
    chatInput.value = '';
}

// Socket Receive Message
socket.on('receive_message', (msg) => {
    // If the chat window with the sender/receiver is open, append it
    if(activeChatUserId && (msg.sender_id === activeChatUserId || msg.receiver_id === activeChatUserId)) {
        appendMessage(msg);
    } else {
        // Show toast and refresh list if not active
        if(msg.sender_id !== currentUserId) {
            showToast('New message received!', 'info');
            loadConversations();
        }
    }
});

// Typing indicator UI
const typingIndicator = document.createElement('div');
typingIndicator.innerHTML = '<small style="color:var(--text-muted);"><i class="fas fa-pen"></i> Typing...</small>';
typingIndicator.style.display = 'none';
typingIndicator.style.padding = '5px 15px';
chatWindow.insertBefore(typingIndicator, chatWindow.lastElementChild);

socket.on('typing', (data) => {
    if(activeChatUserId === data.sender_id) {
        typingIndicator.style.display = 'block';
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
});

socket.on('stop_typing', (data) => {
    if(activeChatUserId === data.sender_id) {
        typingIndicator.style.display = 'none';
    }
});

// Global functions for Toast
function showToast(message, type='info') {
    const container = document.getElementById('toast-container');
    if(!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.style.animation = 'slideIn 0.3s ease forwards';
    toast.innerHTML = `
        <div class="toast-body">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
    `;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 5000);
}
