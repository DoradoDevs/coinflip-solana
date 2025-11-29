/**
 * Coinflip - PVP Solana Wagers
 * Escrow-based system with user authentication
 */

// API Configuration
const API_BASE = 'https://api.coinflipvp.com';

// Auth state
let currentUser = null;
let sessionToken = localStorage.getItem('session_token');

// Global state
let createWagerState = {
    selectedSide: null,
    selectedAmount: null,
    creatorWallet: null,
    escrowAddress: null,
    depositAmount: null,
    wagerId: null
};

let acceptWagerState = {
    wagerId: null,
    amount: null,
    creatorSide: null,
    yourSide: null,
    acceptorWallet: null,
    escrowAddress: null,
    depositAmount: null
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    checkSession();

    // Check for referral code in URL
    checkReferralCode();

    loadActiveWagers();
    loadRecentGames();
    initializeEventListeners();

    // Refresh wagers every 15 seconds
    setInterval(loadActiveWagers, 15000);

    // Refresh recent games every 30 seconds
    setInterval(loadRecentGames, 30000);
});

// ============================================
// AUTHENTICATION
// ============================================

async function checkSession() {
    if (!sessionToken) {
        updateAuthUI(false);
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/me`, {
            headers: { 'Authorization': `Bearer ${sessionToken}` }
        });

        if (response.ok) {
            currentUser = await response.json();
            updateAuthUI(true);
        } else {
            // Session expired
            localStorage.removeItem('session_token');
            sessionToken = null;
            updateAuthUI(false);
        }
    } catch (err) {
        console.error('Session check failed:', err);
        updateAuthUI(false);
    }
}

function checkReferralCode() {
    const params = new URLSearchParams(window.location.search);
    const refCode = params.get('ref');
    if (refCode) {
        localStorage.setItem('referral_code', refCode);
    }
}

function updateAuthUI(isLoggedIn) {
    const authButtons = document.getElementById('authButtons');
    const userMenu = document.getElementById('userMenu');

    if (isLoggedIn && currentUser) {
        authButtons.style.display = 'none';
        userMenu.style.display = 'flex';
        document.getElementById('headerUsername').textContent = currentUser.display_name || currentUser.username;
        document.getElementById('headerTier').textContent = currentUser.tier;
    } else {
        authButtons.style.display = 'flex';
        userMenu.style.display = 'none';
    }
}

function showAuthModal(form = 'login') {
    document.getElementById('authModal').style.display = 'flex';
    switchAuthForm(form);

    // Pre-fill referral code if available
    const savedRefCode = localStorage.getItem('referral_code');
    if (savedRefCode) {
        document.getElementById('registerReferral').value = savedRefCode;
    }
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
    // Clear form inputs
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
    document.getElementById('registerEmail').value = '';
    document.getElementById('registerUsername').value = '';
    document.getElementById('registerPassword').value = '';
}

function switchAuthForm(form) {
    document.getElementById('loginForm').style.display = form === 'login' ? 'block' : 'none';
    document.getElementById('registerForm').style.display = form === 'register' ? 'block' : 'none';
}

async function handleLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    if (!username || !password) {
        alert('Please enter username and password');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }

        // Save session
        sessionToken = data.session_token;
        localStorage.setItem('session_token', sessionToken);

        // Reload user data
        await checkSession();

        closeAuthModal();
        alert('Welcome back!');

    } catch (err) {
        console.error('Login error:', err);
        alert(err.message || 'Login failed. Please try again.');
    }
}

async function handleRegister() {
    const email = document.getElementById('registerEmail').value.trim();
    const username = document.getElementById('registerUsername').value.trim();
    const password = document.getElementById('registerPassword').value;
    const referralCode = document.getElementById('registerReferral').value.trim();

    if (!email || !username || !password) {
        alert('Please fill in all required fields');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email,
                username,
                password,
                referral_code: referralCode || null
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Registration failed');
        }

        // Save session
        sessionToken = data.session_token;
        localStorage.setItem('session_token', sessionToken);

        // Clear saved referral code
        localStorage.removeItem('referral_code');

        // Reload user data
        await checkSession();

        closeAuthModal();
        alert('Account created! Welcome to Coinflip!');

    } catch (err) {
        console.error('Register error:', err);
        alert(err.message || 'Registration failed. Please try again.');
    }
}

async function handleLogout() {
    try {
        await fetch(`${API_BASE}/api/auth/logout`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${sessionToken}` }
        });
    } catch (err) {
        console.error('Logout error:', err);
    }

    // Clear local state
    sessionToken = null;
    currentUser = null;
    localStorage.removeItem('session_token');

    updateAuthUI(false);
    closeProfileModal();
    alert('Logged out successfully');
}

// ============================================
// PROFILE
// ============================================

async function showProfileModal() {
    if (!currentUser) {
        showAuthModal('login');
        return;
    }

    // Refresh user data
    await checkSession();

    if (!currentUser) return;

    // Populate profile data
    document.getElementById('profileGamesPlayed').textContent = currentUser.games_played;
    document.getElementById('profileWinRate').textContent = currentUser.win_rate;
    document.getElementById('profileVolume').textContent = currentUser.total_wagered.toFixed(2);

    const profit = currentUser.total_won - currentUser.total_lost;
    document.getElementById('profileProfit').textContent = profit >= 0 ? `+${profit.toFixed(2)}` : profit.toFixed(2);
    document.getElementById('profileProfit').style.color = profit >= 0 ? 'var(--success)' : 'var(--danger)';

    // Tier
    document.getElementById('profileTier').textContent = currentUser.tier;
    document.getElementById('tierProgressFill').style.width = `${currentUser.tier_progress.progress_percent}%`;

    if (currentUser.tier_progress.next_tier) {
        document.getElementById('tierProgressText').textContent =
            `${currentUser.tier_progress.volume_needed.toFixed(2)} SOL to ${currentUser.tier_progress.next_tier}`;
    } else {
        document.getElementById('tierProgressText').textContent = 'Max tier reached!';
    }

    // Payout wallet
    document.getElementById('profilePayoutWallet').value = currentUser.payout_wallet || '';

    // Referrals
    document.getElementById('customReferralCode').value = currentUser.referral_code;
    document.getElementById('profileReferralLink').textContent = `coinflipvp.com/?ref=${currentUser.referral_code}`;
    document.getElementById('profileReferralLink').href = `https://coinflipvp.com/?ref=${currentUser.referral_code}`;
    document.getElementById('profileReferrals').textContent = currentUser.total_referrals;
    document.getElementById('profilePendingEarnings').textContent = currentUser.pending_referral_earnings.toFixed(4);
    document.getElementById('profileClaimedEarnings').textContent = currentUser.total_referral_claimed.toFixed(4);

    // Tier-based referral rate
    const tierRates = { 'Starter': '0%', 'Bronze': '2.5%', 'Silver': '5%', 'Gold': '7.5%', 'Diamond': '10%' };
    document.getElementById('profileReferralRate').textContent = tierRates[currentUser.tier] || '0%';

    document.getElementById('profileModal').style.display = 'flex';
}

function closeProfileModal() {
    document.getElementById('profileModal').style.display = 'none';
}

async function updatePayoutWallet() {
    const wallet = document.getElementById('profilePayoutWallet').value.trim();

    if (wallet && (wallet.length < 32 || wallet.length > 44)) {
        alert('Please enter a valid Solana wallet address');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/profile/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionToken}`
            },
            body: JSON.stringify({ payout_wallet: wallet })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to update wallet');
        }

        currentUser.payout_wallet = wallet;
        alert('Payout wallet saved!');

    } catch (err) {
        console.error('Update wallet error:', err);
        alert(err.message || 'Failed to update wallet');
    }
}

function copyReferralCode() {
    const code = document.getElementById('customReferralCode').value;
    const link = `https://coinflipvp.com/?ref=${code}`;
    navigator.clipboard.writeText(link).then(() => {
        alert('Referral link copied!');
    });
}

async function updateReferralCode() {
    const newCode = document.getElementById('customReferralCode').value.trim().toUpperCase();

    if (!newCode) {
        alert('Please enter a referral code');
        return;
    }

    if (newCode.length < 3) {
        alert('Referral code must be at least 3 characters');
        return;
    }

    if (newCode.length > 16) {
        alert('Referral code must be 16 characters or less');
        return;
    }

    if (!/^[A-Z0-9_]+$/i.test(newCode)) {
        alert('Referral code can only contain letters, numbers, and underscores');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/profile/referral-code`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionToken}`
            },
            body: JSON.stringify({ referral_code: newCode })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to update referral code');
        }

        // Update local state
        currentUser.referral_code = newCode;

        // Update UI
        document.getElementById('customReferralCode').value = newCode;
        document.getElementById('profileReferralLink').textContent = `coinflipvp.com/?ref=${newCode}`;
        document.getElementById('profileReferralLink').href = `https://coinflipvp.com/?ref=${newCode}`;

        alert('Referral code updated!');

    } catch (err) {
        console.error('Update referral code error:', err);
        alert(err.message || 'Failed to update referral code');
    }
}

async function claimReferralEarnings() {
    if (!currentUser || !currentUser.payout_wallet) {
        alert('Please set your payout wallet first');
        return;
    }

    const btn = document.getElementById('claimReferralBtn');
    btn.disabled = true;
    btn.textContent = 'Claiming...';

    try {
        const response = await fetch(`${API_BASE}/api/referral/claim`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionToken}`
            },
            body: JSON.stringify({ user_wallet: currentUser.payout_wallet })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to claim earnings');
        }

        alert(`Claimed ${data.amount_claimed.toFixed(4)} SOL!`);

        // Refresh profile
        await showProfileModal();

    } catch (err) {
        console.error('Claim error:', err);
        alert(err.message || 'Failed to claim earnings');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Claim Earnings';
    }
}

// ============================================
// AUTH CHECK FOR WAGERS
// ============================================

function requireLogin() {
    if (!currentUser) {
        showAuthModal('register');
        return false;
    }
    return true;
}

/**
 * Initialize Event Listeners
 */
function initializeEventListeners() {
    // Create wager button
    document.getElementById('createWagerBtn').addEventListener('click', openCreateModal);
}

/**
 * Load Active Wagers
 */
async function loadActiveWagers() {
    const container = document.getElementById('activeWagers');

    try {
        const response = await fetch(`${API_BASE}/api/wagers/open`);

        if (!response.ok) {
            throw new Error('Failed to fetch wagers');
        }

        const wagers = await response.json();

        if (!wagers || wagers.length === 0) {
            container.innerHTML = '<div class="no-wagers">No active wagers yet. Be the first to create one!</div>';
            return;
        }

        container.innerHTML = wagers.map(wager => {
            const opponentSide = wager.creator_side === 'heads' ? 'tails' : 'heads';

            return `
                <div class="wager-card" data-wager-id="${wager.id}">
                    <div class="wager-info">
                        <span class="wager-amount">${wager.amount} SOL</span>
                        <span class="wager-side">${wager.creator_side.toUpperCase()}</span>
                        <span class="wager-creator">${wager.creator_wallet.slice(0, 4)}...${wager.creator_wallet.slice(-4)}</span>
                    </div>
                    <button class="btn btn-primary btn-accept" onclick="openAcceptModal('${wager.id}', ${wager.amount}, '${wager.creator_side}')">
                        Accept (${opponentSide.toUpperCase()})
                    </button>
                </div>
            `;
        }).join('');

    } catch (err) {
        console.error('Error loading wagers:', err);
        container.innerHTML = '<div class="error-message">Failed to load wagers. Please refresh.</div>';
    }
}

// ============================================
// CREATE WAGER FLOW
// ============================================

function openCreateModal() {
    // REQUIRE LOGIN
    if (!requireLogin()) return;

    // Reset state
    createWagerState = {
        selectedSide: null,
        selectedAmount: null,
        creatorWallet: null,
        escrowAddress: null,
        depositAmount: null,
        wagerId: null
    };

    // Reset UI
    document.querySelectorAll('.side-btn').forEach(btn => btn.classList.remove('selected'));
    document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById('customAmount').value = '';
    document.getElementById('creatorWallet').value = '';
    document.getElementById('wagerSummary').style.display = 'none';
    document.getElementById('continueBtn').disabled = true;
    document.getElementById('depositTxSignature').value = '';

    // Show step 1
    document.getElementById('step1').style.display = 'block';
    document.getElementById('step2').style.display = 'none';
    document.getElementById('step3').style.display = 'none';

    // Show modal
    document.getElementById('createWagerModal').style.display = 'flex';
}

function closeCreateModal() {
    document.getElementById('createWagerModal').style.display = 'none';
}

function selectSide(side) {
    createWagerState.selectedSide = side;

    document.querySelectorAll('.side-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.side === side);
    });

    updateCreateSummary();
}

function selectAmount(amount) {
    createWagerState.selectedAmount = amount;

    document.querySelectorAll('.amount-btn').forEach(btn => {
        const btnAmount = parseFloat(btn.textContent);
        btn.classList.toggle('selected', btnAmount === amount);
    });

    document.getElementById('customAmount').value = '';
    updateCreateSummary();
}

function useCustomAmount() {
    const input = document.getElementById('customAmount');
    const amount = parseFloat(input.value);

    if (amount && amount >= 0.01) {
        createWagerState.selectedAmount = amount;
        document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
        updateCreateSummary();
    } else {
        alert('Please enter a valid amount (minimum 0.01 SOL)');
    }
}

function updateCreateSummary() {
    const summary = document.getElementById('wagerSummary');
    const continueBtn = document.getElementById('continueBtn');

    if (createWagerState.selectedSide && createWagerState.selectedAmount) {
        const totalDeposit = createWagerState.selectedAmount + 0.025;

        document.getElementById('summarySide').textContent = createWagerState.selectedSide.toUpperCase();
        document.getElementById('summaryAmount').textContent = `${createWagerState.selectedAmount} SOL`;
        document.getElementById('summaryTotal').textContent = `${totalDeposit.toFixed(3)} SOL`;

        summary.style.display = 'block';
        continueBtn.disabled = false;
    } else {
        summary.style.display = 'none';
        continueBtn.disabled = true;
    }
}

async function continueToDeposit() {
    const walletInput = document.getElementById('creatorWallet').value.trim();

    if (!walletInput) {
        alert('Please enter your Solana wallet address to receive winnings');
        return;
    }

    // Basic Solana address validation
    if (walletInput.length < 32 || walletInput.length > 44) {
        alert('Please enter a valid Solana wallet address');
        return;
    }

    createWagerState.creatorWallet = walletInput;

    // Show loading
    const continueBtn = document.getElementById('continueBtn');
    continueBtn.disabled = true;
    continueBtn.textContent = 'Preparing...';

    try {
        // Create wager (prepare step)
        const response = await fetch(`${API_BASE}/api/wager/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                creator_wallet: createWagerState.creatorWallet,
                side: createWagerState.selectedSide,
                amount: createWagerState.selectedAmount
            })
        });

        if (!response.ok) {
            const error = await response.json();
            // Handle FastAPI validation errors (detail can be array or string)
            let errorMsg = 'Failed to create wager';
            if (error.detail) {
                if (typeof error.detail === 'string') {
                    errorMsg = error.detail;
                } else if (Array.isArray(error.detail)) {
                    errorMsg = error.detail.map(e => e.msg || e).join(', ');
                }
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();

        createWagerState.escrowAddress = data.escrow_wallet;
        createWagerState.depositAmount = createWagerState.selectedAmount + 0.025;
        createWagerState.wagerId = data.id;

        // Update step 2 UI
        document.getElementById('depositAmount').textContent = createWagerState.depositAmount.toFixed(3);
        document.getElementById('depositAmount2').textContent = createWagerState.depositAmount.toFixed(3);
        document.getElementById('escrowAddress').textContent = createWagerState.escrowAddress;

        // Show step 2
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';

    } catch (err) {
        console.error('Error creating wager:', err);
        alert(err.message || 'Failed to create wager. Please try again.');
    } finally {
        continueBtn.disabled = false;
        continueBtn.textContent = 'Continue →';
    }
}

function backToStep1() {
    document.getElementById('step1').style.display = 'block';
    document.getElementById('step2').style.display = 'none';
}

function copyEscrowAddress() {
    const address = document.getElementById('escrowAddress').textContent;
    navigator.clipboard.writeText(address).then(() => {
        const btn = document.querySelector('#step2 .copy-btn');
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 2000);
    });
}

async function verifyDeposit() {
    const txSignature = document.getElementById('depositTxSignature').value.trim();

    if (!txSignature) {
        alert('Please enter your transaction signature');
        return;
    }

    // Basic tx signature validation
    if (txSignature.length < 80 || txSignature.length > 100) {
        alert('Please enter a valid transaction signature');
        return;
    }

    const verifyBtn = document.getElementById('verifyDepositBtn');
    verifyBtn.disabled = true;
    verifyBtn.textContent = 'Verifying...';

    try {
        // Verify the deposit
        const response = await fetch(`${API_BASE}/api/wager/${createWagerState.wagerId}/verify-deposit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tx_signature: txSignature
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Deposit verification failed');
        }

        const data = await response.json();

        // Show success
        document.getElementById('newWagerId').textContent = createWagerState.wagerId.slice(0, 8) + '...';
        document.getElementById('newWagerAmount').textContent = `${createWagerState.selectedAmount} SOL`;
        document.getElementById('newWagerSide').textContent = createWagerState.selectedSide.toUpperCase();

        document.getElementById('step2').style.display = 'none';
        document.getElementById('step3').style.display = 'block';

        // Refresh wagers list
        loadActiveWagers();

    } catch (err) {
        console.error('Error verifying deposit:', err);
        alert(err.message || 'Deposit verification failed. Please check your transaction and try again.');
    } finally {
        verifyBtn.disabled = false;
        verifyBtn.textContent = 'Verify Deposit & Create Wager';
    }
}

// ============================================
// ACCEPT WAGER FLOW
// ============================================

function openAcceptModal(wagerId, amount, creatorSide) {
    // REQUIRE LOGIN
    if (!requireLogin()) return;

    const yourSide = creatorSide === 'heads' ? 'tails' : 'heads';
    const totalDeposit = amount + 0.025;

    // Set state
    acceptWagerState = {
        wagerId: wagerId,
        amount: amount,
        creatorSide: creatorSide,
        yourSide: yourSide,
        acceptorWallet: null,
        escrowAddress: null,
        depositAmount: totalDeposit
    };

    // Reset UI
    document.getElementById('acceptorWallet').value = '';
    document.getElementById('acceptTxSignature').value = '';

    // Update step 1 UI
    document.getElementById('acceptAmount').textContent = `${amount} SOL`;
    document.getElementById('acceptCreatorSide').textContent = creatorSide.toUpperCase();
    document.getElementById('acceptYourSide').textContent = yourSide.toUpperCase();
    document.getElementById('acceptTotal').textContent = `${totalDeposit.toFixed(3)} SOL`;

    // Show step 1
    document.getElementById('acceptStep1').style.display = 'block';
    document.getElementById('acceptStep2').style.display = 'none';
    document.getElementById('acceptStep3').style.display = 'none';

    // Show modal
    document.getElementById('acceptWagerModal').style.display = 'flex';
}

function closeAcceptModal() {
    document.getElementById('acceptWagerModal').style.display = 'none';
}

async function continueToAcceptDeposit() {
    const walletInput = document.getElementById('acceptorWallet').value.trim();

    if (!walletInput) {
        alert('Please enter your Solana wallet address to receive winnings');
        return;
    }

    if (walletInput.length < 32 || walletInput.length > 44) {
        alert('Please enter a valid Solana wallet address');
        return;
    }

    acceptWagerState.acceptorWallet = walletInput;

    const continueBtn = document.getElementById('acceptContinueBtn');
    continueBtn.disabled = true;
    continueBtn.textContent = 'Preparing...';

    try {
        // Prepare accept (get escrow address)
        const response = await fetch(`${API_BASE}/api/wager/${acceptWagerState.wagerId}/prepare-accept`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                acceptor_wallet: acceptWagerState.acceptorWallet
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to prepare acceptance');
        }

        const data = await response.json();

        acceptWagerState.escrowAddress = data.escrow_wallet;

        // Update step 2 UI
        document.getElementById('acceptDepositAmount').textContent = acceptWagerState.depositAmount.toFixed(3);
        document.getElementById('acceptEscrowAddress').textContent = acceptWagerState.escrowAddress;

        // Show step 2
        document.getElementById('acceptStep1').style.display = 'none';
        document.getElementById('acceptStep2').style.display = 'block';

    } catch (err) {
        console.error('Error preparing accept:', err);
        alert(err.message || 'Failed to prepare. Please try again.');
    } finally {
        continueBtn.disabled = false;
        continueBtn.textContent = 'Continue to Deposit →';
    }
}

function backToAcceptStep1() {
    document.getElementById('acceptStep1').style.display = 'block';
    document.getElementById('acceptStep2').style.display = 'none';
}

function copyAcceptEscrowAddress() {
    const address = document.getElementById('acceptEscrowAddress').textContent;
    navigator.clipboard.writeText(address).then(() => {
        const btn = document.querySelector('#acceptStep2 .copy-btn');
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 2000);
    });
}

async function verifyAcceptDeposit() {
    const txSignature = document.getElementById('acceptTxSignature').value.trim();

    if (!txSignature) {
        alert('Please enter your transaction signature');
        return;
    }

    if (txSignature.length < 80 || txSignature.length > 100) {
        alert('Please enter a valid transaction signature');
        return;
    }

    const verifyBtn = document.getElementById('verifyAcceptBtn');
    verifyBtn.disabled = true;
    verifyBtn.textContent = 'Verifying & Flipping...';

    try {
        // Accept wager and execute coinflip
        const response = await fetch(`${API_BASE}/api/wager/${acceptWagerState.wagerId}/accept`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                acceptor_wallet: acceptWagerState.acceptorWallet,
                deposit_tx_signature: txSignature,
                source: 'web'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to execute coinflip');
        }

        const result = await response.json();

        // Show result
        showGameResult(result);

        // Refresh wagers list
        loadActiveWagers();

    } catch (err) {
        console.error('Error accepting wager:', err);
        alert(err.message || 'Failed to execute coinflip. Please try again.');
    } finally {
        verifyBtn.disabled = false;
        verifyBtn.textContent = 'Verify & Execute Coinflip';
    }
}

function showGameResult(result) {
    const resultContainer = document.getElementById('gameResultContent');
    const isWinner = result.winner_wallet === acceptWagerState.acceptorWallet;
    const payout = (acceptWagerState.amount * 2) * 0.98;

    let html = '';

    if (isWinner) {
        html = `
            <div class="result-icon win-icon">WIN</div>
            <h2 class="result-title win">YOU WON!</h2>
            <div class="result-details">
                <div class="result-row">
                    <span>Coin Result:</span>
                    <span>${result.result.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Your Side:</span>
                    <span>${acceptWagerState.yourSide.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Payout:</span>
                    <span style="color: var(--success); font-weight: 700;">${payout.toFixed(4)} SOL</span>
                </div>
            </div>
            <p class="fairness-note">
                Provably Fair<br>
                <small>Blockhash: ${result.blockhash ? result.blockhash.slice(0, 20) + '...' : 'N/A'}</small>
            </p>
        `;
    } else {
        html = `
            <div class="result-icon lose-icon">LOSS</div>
            <h2 class="result-title lose">YOU LOST</h2>
            <div class="result-details">
                <div class="result-row">
                    <span>Coin Result:</span>
                    <span>${result.result.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Your Side:</span>
                    <span>${acceptWagerState.yourSide.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Lost:</span>
                    <span style="color: var(--danger); font-weight: 700;">${acceptWagerState.amount} SOL</span>
                </div>
            </div>
            <p class="fairness-note">
                Provably Fair<br>
                <small>Blockhash: ${result.blockhash ? result.blockhash.slice(0, 20) + '...' : 'N/A'}</small>
            </p>
        `;
    }

    resultContainer.innerHTML = html;

    document.getElementById('acceptStep2').style.display = 'none';
    document.getElementById('acceptStep3').style.display = 'block';
}

// ============================================
// RECENT GAMES
// ============================================

async function loadRecentGames() {
    const container = document.getElementById('recentGames');

    try {
        const response = await fetch(`${API_BASE}/api/games/recent?limit=10`);

        if (!response.ok) {
            throw new Error('Failed to fetch recent games');
        }

        const games = await response.json();

        // Filter to only games from the last 24 hours
        const twentyFourHoursAgo = Date.now() - (24 * 60 * 60 * 1000);
        const recentGames = games.filter(game => {
            const gameTime = new Date(game.completed_at).getTime();
            return gameTime >= twentyFourHoursAgo;
        });

        if (!recentGames || recentGames.length === 0) {
            container.innerHTML = '<div class="no-games">No games in the past 24h</div>';
            return;
        }

        // Use filtered games
        const gamesToDisplay = recentGames;

        container.innerHTML = gamesToDisplay.map(game => {
            const winnerShort = game.winner_wallet ?
                `${game.winner_wallet.slice(0, 4)}...${game.winner_wallet.slice(-4)}` : 'N/A';
            const payout = (game.amount * 2 * 0.98).toFixed(4);
            const timeAgo = getTimeAgo(new Date(game.completed_at));
            const blockhashShort = game.proof && game.proof.blockhash ?
                `${game.proof.blockhash.slice(0, 12)}...${game.proof.blockhash.slice(-8)}` : 'N/A';

            return `
                <div class="recent-game-card" onclick="showProofModal('${game.game_id}', ${JSON.stringify(game.proof).replace(/"/g, '&quot;')})">
                    <div class="game-info">
                        <span class="game-result ${game.result}">${game.result.toUpperCase()}</span>
                        <span class="game-amount">${game.amount} SOL</span>
                        <span class="game-winner">${winnerShort} won ${payout} SOL</span>
                    </div>
                    <div class="game-meta">
                        <span class="game-time">${timeAgo}</span>
                        <span class="verify-link">Verify</span>
                    </div>
                    <div class="game-blockhash">
                        <span class="blockhash-label">Blockhash:</span>
                        <code class="blockhash-value">${blockhashShort}</code>
                    </div>
                </div>
            `;
        }).join('');

    } catch (err) {
        console.error('Error loading recent games:', err);
        container.innerHTML = '<div class="no-games">Failed to load recent games.</div>';
    }
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

function showProofModal(gameId, proof) {
    const modal = document.createElement('div');
    modal.className = 'modal proof-modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content proof-content">
            <span class="modal-close" onclick="this.parentElement.parentElement.remove()">&times;</span>
            <h2>Provably Fair Proof</h2>

            <div class="proof-section">
                <h3>Game Details</h3>
                <div class="proof-row">
                    <span>Game ID:</span>
                    <code>${gameId}</code>
                </div>
                <div class="proof-row">
                    <span>Result:</span>
                    <span class="result-badge ${proof.actual_result}">${proof.actual_result.toUpperCase()}</span>
                </div>
                <div class="proof-row">
                    <span>Verified:</span>
                    <span class="${proof.verified ? 'verified' : 'failed'}">${proof.verified ? 'VERIFIED' : 'FAILED'}</span>
                </div>
            </div>

            <div class="proof-section">
                <h3>Verification Data</h3>
                <div class="proof-row">
                    <span>Blockhash:</span>
                    <code class="small">${proof.blockhash}</code>
                </div>
                <div class="proof-row">
                    <span>SHA-256 Hash:</span>
                    <code class="small">${proof.hash}</code>
                </div>
                <div class="proof-row">
                    <span>First Byte (hex):</span>
                    <code>${proof.first_byte_hex}</code>
                </div>
                <div class="proof-row">
                    <span>First Byte (decimal):</span>
                    <code>${proof.first_byte}</code>
                </div>
                <div class="proof-row">
                    <span>Is Even:</span>
                    <span>${proof.is_even ? 'Yes (HEADS)' : 'No (TAILS)'}</span>
                </div>
            </div>

            <div class="proof-section">
                <h3>Algorithm</h3>
                <p class="algorithm-text">${proof.algorithm}</p>
                <p class="verify-note">You can verify this yourself:<br>
                SHA256("${proof.blockhash}${gameId}") = ${proof.hash.slice(0, 20)}...</p>
            </div>

            <a href="https://solscan.io/tx/${proof.blockhash}" target="_blank" class="btn btn-secondary">
                View on Solscan
            </a>
        </div>
    `;

    document.body.appendChild(modal);

    // Close on outside click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

// ============================================
// FAIRNESS INFO
// ============================================

function showFairnessInfo() {
    // Create a proper modal instead of alert
    const modal = document.createElement('div');
    modal.className = 'modal proof-modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content fairness-content">
            <span class="modal-close" onclick="this.parentElement.parentElement.remove()">&times;</span>
            <h2>Provably Fair - Exact 50/50</h2>

            <div class="fairness-section">
                <h3>How It Works</h3>
                <p>Our coinflip uses Solana's blockhash for true on-chain randomness:</p>
                <ol>
                    <li>When you play, we fetch the latest Solana blockhash</li>
                    <li>We compute: <code>SHA-256(blockhash + game_id)</code></li>
                    <li>First byte determines result: <strong>even = HEADS, odd = TAILS</strong></li>
                </ol>
            </div>

            <div class="fairness-section highlight-box">
                <h3>Mathematically Exact 50/50</h3>
                <p>The SHA-256 first byte has 256 possible values (0-255):</p>
                <ul>
                    <li><strong>128 even values</strong> (0,2,4...254) = HEADS (50%)</li>
                    <li><strong>128 odd values</strong> (1,3,5...255) = TAILS (50%)</li>
                </ul>
                <p class="emphasis">This is a mathematically perfect 50/50 split - neither player has an edge.</p>
            </div>

            <div class="fairness-section">
                <h3>Verify Any Game</h3>
                <p>Every result can be independently verified:</p>
                <ul>
                    <li>Blockhash is from Solana blockchain (unpredictable, immutable)</li>
                    <li>Game ID is generated before the blockhash is known</li>
                    <li>Click any recent game to see full verification data</li>
                </ul>
            </div>

            <div class="fairness-section">
                <h3>Security</h3>
                <ul>
                    <li>All funds held in unique escrow wallets until flip completes</li>
                    <li>No single point of failure</li>
                    <li>Winner paid automatically from escrow</li>
                </ul>
            </div>

            <button class="btn btn-primary" onclick="this.parentElement.parentElement.remove()">Got It</button>
        </div>
    `;

    document.body.appendChild(modal);

    // Close on outside click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

// ============================================
// SUPPORT TICKET MODAL
// ============================================

function showSupportModal(ticketType = 'support') {
    const modal = document.getElementById('supportModal');
    const titleEl = document.getElementById('supportModalTitle');
    const typeSelect = document.getElementById('supportType');
    const subjectInput = document.getElementById('supportSubject');
    const messageInput = document.getElementById('supportMessage');
    const emailInput = document.getElementById('supportEmail');
    const statusEl = document.getElementById('supportStatus');

    // Reset form
    document.getElementById('supportForm').reset();
    statusEl.style.display = 'none';

    // Set type based on parameter
    typeSelect.value = ticketType;

    // Set title based on type
    if (ticketType === 'password_reset') {
        titleEl.textContent = 'Password Reset Request';
        subjectInput.value = 'Password Reset Request';
        messageInput.placeholder = 'Please enter your account email and any additional information...';
    } else {
        titleEl.textContent = 'Contact Support';
        subjectInput.value = '';
        messageInput.placeholder = 'Describe your issue in detail...';
    }

    // Pre-fill email if logged in
    if (currentUser && currentUser.email) {
        emailInput.value = currentUser.email;
    }

    modal.style.display = 'flex';
}

function closeSupportModal() {
    document.getElementById('supportModal').style.display = 'none';
}

async function submitSupportTicket(event) {
    event.preventDefault();

    const emailInput = document.getElementById('supportEmail');
    const typeSelect = document.getElementById('supportType');
    const subjectInput = document.getElementById('supportSubject');
    const messageInput = document.getElementById('supportMessage');
    const submitBtn = document.getElementById('supportSubmitBtn');
    const statusEl = document.getElementById('supportStatus');

    const email = emailInput.value.trim();
    const ticketType = typeSelect.value;
    const subject = subjectInput.value.trim();
    const message = messageInput.value.trim();

    // Validation
    if (!email || !subject || !message) {
        statusEl.textContent = 'Please fill in all fields';
        statusEl.style.display = 'block';
        statusEl.style.color = '#FF4757';
        return;
    }

    if (message.length < 10) {
        statusEl.textContent = 'Message must be at least 10 characters';
        statusEl.style.display = 'block';
        statusEl.style.color = '#FF4757';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';
    statusEl.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/api/support/ticket`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: email,
                ticket_type: ticketType,
                subject: subject,
                message: message
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to submit ticket');
        }

        // Success
        statusEl.textContent = `Ticket submitted! ID: ${data.ticket_id}. We will respond to your email.`;
        statusEl.style.display = 'block';
        statusEl.style.color = '#14F195';

        // Reset form after short delay
        setTimeout(() => {
            closeSupportModal();
        }, 3000);

    } catch (err) {
        console.error('Support ticket error:', err);
        statusEl.textContent = err.message || 'Failed to submit ticket. Please try again.';
        statusEl.style.display = 'block';
        statusEl.style.color = '#FF4757';
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Ticket';
    }
}
