// Frontend Authentication Handler for TicketFlow

const API_URL = (window.location.origin === 'null' || window.location.origin.startsWith('file:')) ? 'http://127.0.0.1:8000' : window.location.origin;

document.addEventListener('DOMContentLoaded', () => {
    // --- State Toggles & View Controls ---
    const signinContainer = document.getElementById('signin-container');
    const signupContainer = document.getElementById('signup-container');
    const linkToSignup = document.getElementById('link-to-signup');
    const linkToSignin = document.getElementById('link-to-signin');

    linkToSignup.addEventListener('click', (e) => {
        e.preventDefault();
        signinContainer.classList.remove('active');
        signupContainer.classList.add('active');
        clearForms();
    });

    linkToSignin.addEventListener('click', (e) => {
        e.preventDefault();
        signupContainer.classList.remove('active');
        signinContainer.classList.add('active');
        clearForms();
    });

    // --- Password Visibility Toggles ---
    setupPasswordToggle('signin-password', 'toggle-signin-password');
    setupPasswordToggle('signup-password', 'toggle-signup-password');

    // --- Form Submissions ---
    const signinForm = document.getElementById('signin-form');
    const signupForm = document.getElementById('signup-form');

    signinForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const emailInput = document.getElementById('signin-email');
        const passwordInput = document.getElementById('signin-password');
        const btnSignin = document.getElementById('btn-signin');

        // Validation
        const email = emailInput.value.trim();
        const password = passwordInput.value;

        if (!email || !password) {
            showToast('Please fill in all fields.', 'error');
            return;
        }

        if (!validateEmail(email)) {
            showToast('Please enter a valid email address.', 'error');
            return;
        }

        // Send API Request
        try {
            setLoading(btnSignin, true, 'Signing In...');
            
            const response = await fetch(`${API_URL}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            let data;
            try {
                data = await response.json();
            } catch (jsonErr) {
                throw new Error(`Failed to parse server response (Status ${response.status}). Please make sure your Python server is running and your PostgreSQL database is reachable.`);
            }

            if (!response.ok) {
                throw new Error(data.detail || 'Authentication failed. Please check your credentials.');
            }

            // Save Token & User Info
            localStorage.setItem('access_token', data.access_token);
            showToast('Sign-in successful! Redirecting...', 'success');
            
            // Redirect to Dashboard
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1000);

        } catch (error) {
            console.error('Sign-in error:', error);
            showToast(error.message, 'error');
            setLoading(btnSignin, false, 'Sign In');
        }
    });

    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const fullnameInput = document.getElementById('signup-fullname');
        const emailInput = document.getElementById('signup-email');
        const passwordInput = document.getElementById('signup-password');
        const btnSignup = document.getElementById('btn-signup');

        // Validation
        const fullName = fullnameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passwordInput.value;

        if (!fullName || !email || !password) {
            showToast('Please fill in all fields.', 'error');
            return;
        }

        if (!validateEmail(email)) {
            showToast('Please enter a valid email address.', 'error');
            return;
        }

        if (password.length < 6) {
            showToast('Password must be at least 6 characters long.', 'error');
            return;
        }

        // Send API Request
        try {
            setLoading(btnSignup, true, 'Creating Account...');

            const response = await fetch(`${API_URL}/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    full_name: fullName, 
                    email: email, 
                    password: password 
                })
            });

            let data;
            try {
                data = await response.json();
            } catch (jsonErr) {
                throw new Error(`Failed to parse server response (Status ${response.status}). Please make sure your Python server is running and your PostgreSQL database is reachable.`);
            }

            if (!response.ok) {
                throw new Error(data.detail || 'Registration failed. Please try again.');
            }

            // Successful Registration
            showToast('Account created successfully! Please sign in.', 'success');
            
            // Switch to Login View and auto-fill email
            setTimeout(() => {
                signupContainer.classList.remove('active');
                signinContainer.classList.add('active');
                clearForms();
                document.getElementById('signin-email').value = email;
                document.getElementById('signin-password').focus();
                setLoading(btnSignup, false, 'Create Account');
            }, 1200);

        } catch (error) {
            console.error('Sign-up error:', error);
            showToast(error.message, 'error');
            setLoading(btnSignup, false, 'Create Account');
        }
    });

    // Check query params for session expiration redirect
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('expired') === 'true') {
        showToast('Your session has expired. Please sign in again.', 'info');
        // Clean URL parameter
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

// --- Utility Helpers ---

function setupPasswordToggle(inputId, buttonId) {
    const input = document.getElementById(inputId);
    const button = document.getElementById(buttonId);
    
    if (!input || !button) return;

    button.addEventListener('click', () => {
        const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
        input.setAttribute('type', type);
        
        // Toggle SVG Eye Slash representation
        const eyeIcon = button.querySelector('.eye-icon');
        if (type === 'text') {
            eyeIcon.innerHTML = `
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
            `;
        } else {
            eyeIcon.innerHTML = `
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
            `;
        }
    });
}

function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function setLoading(button, isLoading, text) {
    const span = button.querySelector('span');
    if (isLoading) {
        button.disabled = true;
        button.innerHTML = `<span class="spinner"></span> <span>${text}</span>`;
    } else {
        button.disabled = false;
        button.innerHTML = `<span>${text}</span>`;
    }
}

function clearForms() {
    document.getElementById('signin-form').reset();
    document.getElementById('signup-form').reset();
}

// Toast Helper
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Choose appropriate SVG Icon based on type
    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'error') {
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${iconSvg} <span>${message}</span>`;
    container.appendChild(toast);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
