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
            console.log('✅ Session refreshed - User data:', {
                username: currentUser.username,
                games_played: currentUser.games_played,
                games_won: currentUser.games_won,
                total_wagered: currentUser.total_wagered,
                total_won: currentUser.total_won,
                total_lost: currentUser.total_lost,
                tier: currentUser.tier,
                tier_progress: currentUser.tier_progress
            });
            updateAuthUI(true);
        } else {
            // Session expired
            console.log('❌ Session expired');
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
    const registerReferralEl = document.getElementById('registerReferral');
    if (savedRefCode && registerReferralEl) {
        registerReferralEl.value = savedRefCode;
    }
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
    // Clear form inputs (with null checks)
    const loginUsername = document.getElementById('loginUsername');
    const loginPassword = document.getElementById('loginPassword');
    const registerEmail = document.getElementById('registerEmail');
    const registerUsername = document.getElementById('registerUsername');
    const registerPassword = document.getElementById('registerPassword');
    const registerReferral = document.getElementById('registerReferral');

    if (loginUsername) loginUsername.value = '';
    if (loginPassword) loginPassword.value = '';
    if (registerEmail) registerEmail.value = '';
    if (registerUsername) registerUsername.value = '';
    if (registerPassword) registerPassword.value = '';
    if (registerReferral) registerReferral.value = '';
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
    const wallet = document.getElementById('registerWallet').value.trim();
    const referralEl = document.getElementById('registerReferral');
    const referralCode = referralEl ? referralEl.value.trim() : '';

    if (!email || !username || !password || !wallet) {
        alert('Please fill in all required fields (including wallet address)');
        return;
    }

    // Basic Solana wallet validation (base58, 32-44 chars)
    if (wallet.length < 32 || wallet.length > 44) {
        alert('Invalid Solana wallet address. Please check and try again.');
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
                payout_wallet: wallet,
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

    console.log('👤 Profile data:', currentUser);

    // Populate profile data with fallbacks
    const gamesPlayed = currentUser.games_played || 0;
    const totalWon = currentUser.total_won || 0;
    const totalLost = currentUser.total_lost || 0;
    const totalWagered = currentUser.total_wagered || 0;

    // Calculate win rate
    let winRate = '0.0%';
    if (gamesPlayed > 0) {
        const wins = currentUser.games_won || 0;
        const rate = (wins / gamesPlayed) * 100;
        winRate = rate.toFixed(1) + '%';
    }

    document.getElementById('profileGamesPlayed').textContent = gamesPlayed;
    document.getElementById('profileWinRate').textContent = winRate;
    document.getElementById('profileVolume').textContent = totalWagered.toFixed(2);

    const profit = totalWon - totalLost;
    document.getElementById('profileProfit').textContent = profit >= 0 ? `+${profit.toFixed(2)}` : profit.toFixed(2);
    document.getElementById('profileProfit').style.color = profit >= 0 ? 'var(--success)' : 'var(--danger)';

    // Tier
    document.getElementById('profileTier').textContent = currentUser.tier || 'Starter';

    // Tier progress
    if (currentUser.tier_progress) {
        const progressPercent = currentUser.tier_progress.progress_percent || 0;
        document.getElementById('tierProgressFill').style.width = `${progressPercent}%`;

        if (currentUser.tier_progress.next_tier) {
            const volumeNeeded = currentUser.tier_progress.volume_needed || 0;
            document.getElementById('tierProgressText').textContent =
                `${volumeNeeded.toFixed(2)} SOL to ${currentUser.tier_progress.next_tier}`;
        } else {
            document.getElementById('tierProgressText').textContent = 'Max tier reached!';
        }
    } else {
        document.getElementById('tierProgressFill').style.width = '0%';
        document.getElementById('tierProgressText').textContent = '10.00 SOL to Bronze';
    }

    console.log('👤 Profile updated - Games:', gamesPlayed, 'Win Rate:', winRate, 'Volume:', totalWagered)

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

    // Token holder benefits (only show if user holds tokens)
    const tokenSection = document.getElementById('tokenBenefitsSection');
    if (currentUser.token_tier && currentUser.token_balance > 0) {
        tokenSection.style.display = 'block';
        document.getElementById('profileTokenTier').textContent = currentUser.token_tier;
        document.getElementById('profileTokenBalance').textContent = currentUser.token_balance.toLocaleString();
        document.getElementById('profileTokenDiscount').textContent = `${(currentUser.token_discount * 100).toFixed(0)}%`;
        document.getElementById('profileCombinedDiscount').textContent = `${(currentUser.combined_discount * 100).toFixed(0)}%`;
        document.getElementById('profileEffectiveFee').textContent = `${(currentUser.effective_fee_rate * 100).toFixed(2)}%`;
    } else {
        tokenSection.style.display = 'none';
    }

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
            // Show username if available, otherwise show shortened wallet
            const creatorDisplay = wager.creator_username ||
                `${wager.creator_wallet.slice(0, 4)}...${wager.creator_wallet.slice(-4)}`;

            // Check if current user is the creator
            const isCreator = currentUser && currentUser.payout_wallet === wager.creator_wallet;
            // Check if someone is accepting this wager
            const isBeingAccepted = wager.is_accepting;

            // Determine which button to show
            let actionButton = '';
            if (isCreator) {
                if (isBeingAccepted) {
                    // Someone is accepting - show disabled state
                    actionButton = `
                        <button class="btn btn-secondary" disabled style="opacity: 0.6;">
                            Being Accepted...
                        </button>
                    `;
                } else {
                    // Creator can cancel their own wager
                    actionButton = `
                        <button class="btn btn-danger btn-cancel" onclick="cancelWager('${wager.id}')">
                            Cancel
                        </button>
                    `;
                }
            } else {
                if (isBeingAccepted) {
                    // Someone else is accepting
                    actionButton = `
                        <button class="btn btn-secondary" disabled style="opacity: 0.6;">
                            Being Accepted...
                        </button>
                    `;
                } else {
                    // Normal accept button
                    actionButton = `
                        <button class="btn btn-primary btn-accept" onclick="openAcceptModal('${wager.id}', ${wager.amount}, '${wager.creator_side}')">
                            Accept (${opponentSide.toUpperCase()})
                        </button>
                    `;
                }
            }

            return `
                <div class="wager-card" data-wager-id="${wager.id}">
                    <div class="wager-info">
                        <span class="wager-amount">${wager.amount} SOL</span>
                        <span class="wager-side">${wager.creator_side.toUpperCase()}</span>
                        <span class="wager-creator">${creatorDisplay}${isCreator ? ' (You)' : ''}</span>
                    </div>
                    ${actionButton}
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
    document.getElementById('wagerSummary').style.display = 'none';
    document.getElementById('continueBtn').disabled = true;

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
        const totalDeposit = createWagerState.selectedAmount;

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
    // Use payout wallet from logged-in user's account
    if (!currentUser || !currentUser.payout_wallet) {
        alert('You must be logged in with a payout wallet set to create wagers.\n\nPlease set your payout wallet in your profile.');
        return;
    }

    createWagerState.creatorWallet = currentUser.payout_wallet;

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
        createWagerState.depositAmount = createWagerState.selectedAmount;
        createWagerState.wagerId = data.id;

        // Update step 2 UI
        document.getElementById('depositAmount').textContent = createWagerState.depositAmount.toFixed(3);
        document.getElementById('escrowAddress').textContent = createWagerState.escrowAddress;

        // Show step 2
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';

        // Start monitoring for deposit
        startCreateDepositMonitoring(createWagerState.wagerId);

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
    const totalDeposit = amount;

    // Use payout wallet from user's account
    const acceptorWallet = currentUser.payout_wallet;
    if (!acceptorWallet) {
        alert('You must set a payout wallet in your profile before accepting wagers.\n\nPlease update your profile with your Solana wallet address.');
        return;
    }

    // Set state
    acceptWagerState = {
        wagerId: wagerId,
        amount: amount,
        creatorSide: creatorSide,
        yourSide: yourSide,
        acceptorWallet: acceptorWallet,
        escrowAddress: null,
        depositAmount: totalDeposit
    };

    // Display the wallet that will receive winnings
    const walletDisplay = `${acceptorWallet.slice(0, 6)}...${acceptorWallet.slice(-6)}`;
    document.getElementById('acceptorWalletDisplay').textContent = walletDisplay;

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
    // If user was in the middle of accepting (escrow was created), abandon it
    if (acceptWagerState.escrowAddress && acceptWagerState.acceptorWallet) {
        // Call abandon endpoint (fire and forget with small delay for UX)
        setTimeout(async () => {
            try {
                await fetch(`${API_BASE}/api/wager/${acceptWagerState.wagerId}/abandon-accept`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        acceptor_wallet: acceptWagerState.acceptorWallet
                    })
                });
                console.log('Abandoned accept for wager:', acceptWagerState.wagerId);
                loadActiveWagers(); // Refresh to show cancel button again
            } catch (err) {
                console.error('Failed to abandon accept:', err);
            }
        }, 3000); // 3 second delay as requested
    }
    document.getElementById('acceptWagerModal').style.display = 'none';
}

/**
 * Cancel an open wager (creator only)
 */
async function cancelWager(wagerId) {
    if (!currentUser || !currentUser.payout_wallet) {
        alert('You must be logged in to cancel a wager');
        return;
    }

    if (!confirm('Are you sure you want to cancel this wager? Your full wager amount will be refunded.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/wager/cancel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${sessionToken}`
            },
            body: JSON.stringify({
                wager_id: wagerId,
                creator_wallet: currentUser.payout_wallet
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to cancel wager');
        }

        const data = await response.json();
        alert(`Wager cancelled! Refunded ${data.refund_amount} SOL to your wallet.`);
        loadActiveWagers(); // Refresh the list

    } catch (err) {
        console.error('Cancel wager error:', err);
        alert('Failed to cancel wager: ' + err.message);
    }
}

async function continueToAcceptDeposit() {
    // Wallet is already set from acceptWager()
    if (!acceptWagerState.acceptorWallet) {
        alert('No payout wallet found. Please set one in your profile.');
        return;
    }

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

        // Start monitoring for deposit
        startDepositMonitoring(acceptWagerState.wagerId, 'acceptor');

    } catch (err) {
        console.error('Error preparing accept:', err);
        alert(err.message || 'Failed to prepare. Please try again.');
    } finally {
        continueBtn.disabled = false;
        continueBtn.textContent = 'Continue to Deposit →';
    }
}

let depositMonitoringInterval = null;

function startDepositMonitoring(wagerId, depositType) {
    // Clear any existing interval
    if (depositMonitoringInterval) {
        clearInterval(depositMonitoringInterval);
    }

    let attempts = 0;
    const maxAttempts = 150; // 5 minutes (150 * 2 seconds)

    const checkDeposit = async () => {
        attempts++;

        try {
            const response = await fetch(`${API_BASE}/api/wager/${wagerId}/check-deposit`);
            const data = await response.json();

            // Log EVERY response to see what's happening
            console.log(`[Attempt ${attempts}] Check deposit response:`, data);

            // Log debug info if available
            if (data.debug) {
                console.log('🔍 Deposit check debug:', data.debug);
            }

            if (data.deposit_found && data.transaction_signature) {
                // Deposit found!
                clearInterval(depositMonitoringInterval);
                depositMonitoringInterval = null;

                console.log('✅ Deposit detected:', data.transaction_signature);

                // Update status
                document.getElementById('depositStatusText').textContent = 'Deposit received! Executing coinflip...';

                // Execute the wager acceptance
                await executeAcceptWager(data.transaction_signature);

            } else if (attempts >= maxAttempts) {
                // Timeout
                clearInterval(depositMonitoringInterval);
                depositMonitoringInterval = null;

                document.getElementById('depositStatusText').textContent = 'Timeout waiting for deposit';
                alert('Deposit not detected within 5 minutes. Please try again or contact support.');

            } else {
                // Still waiting
                const elapsed = Math.floor(attempts * 2);
                document.getElementById('depositStatusText').textContent =
                    `Monitoring escrow wallet (${elapsed}s elapsed)...`;
            }

        } catch (err) {
            console.error('Error checking deposit:', err);
        }
    };

    // Check immediately
    checkDeposit();

    // Then check every 2 seconds
    depositMonitoringInterval = setInterval(checkDeposit, 2000);
}

function cancelAcceptDeposit() {
    // Stop monitoring
    if (depositMonitoringInterval) {
        clearInterval(depositMonitoringInterval);
        depositMonitoringInterval = null;
    }

    // Close modal
    closeAcceptModal();
}

function startCreateDepositMonitoring(wagerId) {
    // Clear any existing interval
    if (depositMonitoringInterval) {
        clearInterval(depositMonitoringInterval);
    }

    let attempts = 0;
    const maxAttempts = 150; // 5 minutes (150 * 2 seconds)

    const checkDeposit = async () => {
        attempts++;

        try {
            const response = await fetch(`${API_BASE}/api/wager/${wagerId}/check-deposit`);
            const data = await response.json();

            // Log EVERY response to see what's happening
            console.log(`[Attempt ${attempts}] Check deposit response:`, data);

            // Log debug info if available
            if (data.debug) {
                console.log('🔍 Deposit check debug:', data.debug);
            }

            if (data.deposit_found && data.transaction_signature) {
                // Deposit found!
                clearInterval(depositMonitoringInterval);
                depositMonitoringInterval = null;

                console.log('✅ Deposit detected:', data.transaction_signature);

                // Update status
                document.getElementById('createDepositStatusText').textContent = 'Deposit received! Activating wager...';

                // Activate the wager
                await activateWager(wagerId, data.transaction_signature);

            } else if (attempts >= maxAttempts) {
                // Timeout
                clearInterval(depositMonitoringInterval);
                depositMonitoringInterval = null;

                document.getElementById('createDepositStatusText').textContent = 'Timeout waiting for deposit';
                alert('Deposit not detected within 5 minutes. Please try again or contact support.');

            } else {
                // Still waiting
                const elapsed = Math.floor(attempts * 2);
                document.getElementById('createDepositStatusText').textContent =
                    `Monitoring escrow wallet (${elapsed}s elapsed)...`;
            }

        } catch (err) {
            console.error('Error checking deposit:', err);
        }
    };

    // Check immediately
    checkDeposit();

    // Then check every 2 seconds
    depositMonitoringInterval = setInterval(checkDeposit, 2000);
}

function cancelCreateDeposit() {
    // Stop monitoring
    if (depositMonitoringInterval) {
        clearInterval(depositMonitoringInterval);
        depositMonitoringInterval = null;
    }

    // Close modal
    closeCreateModal();
}

async function activateWager(wagerId, txSignature) {
    try {
        const response = await fetch(`${API_BASE}/api/wager/${wagerId}/verify-deposit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tx_signature: txSignature
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to activate wager');
        }

        const result = await response.json();

        console.log('✅ Wager activated successfully:', result);

        // Show success screen
        document.getElementById('newWagerId').textContent = result.wager_id;
        document.getElementById('newWagerAmount').textContent = `${createWagerState.selectedAmount} SOL`;
        document.getElementById('newWagerSide').textContent = createWagerState.selectedSide.toUpperCase();

        document.getElementById('step2').style.display = 'none';
        document.getElementById('step3').style.display = 'block';

        // Refresh wagers list
        loadActiveWagers();

    } catch (err) {
        console.error('❌ Error activating wager:', err);
        console.error('Error details:', err.message, err.stack);
        alert(err.message || 'Failed to activate wager. Please contact support.');
    }
}

async function executeAcceptWager(txSignature) {
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (sessionToken) {
            headers['Authorization'] = `Bearer ${sessionToken}`;
        }

        // Show loading overlay
        const loadingOverlay = document.createElement('div');
        loadingOverlay.id = 'verifyingOverlay';
        loadingOverlay.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0, 0, 0, 0.95); z-index: 999998;
            display: flex; flex-direction: column; align-items: center;
            justify-content: center; padding: 20px;
        `;
        loadingOverlay.innerHTML = `
            <div style="text-align: center;">
                <div class="spinner" style="
                    border: 4px solid rgba(255, 215, 0, 0.3);
                    border-top: 4px solid #FFD700;
                    border-radius: 50%;
                    width: 60px; height: 60px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                "></div>
                <h2 style="color: #FFD700; font-size: 1.8rem; margin: 10px 0;">Executing Coinflip...</h2>
                <p style="color: #aaa; font-size: 1.1rem;">Verifying on-chain & flipping coin</p>
            </div>
        `;
        document.body.appendChild(loadingOverlay);

        const response = await fetch(`${API_BASE}/api/wager/${acceptWagerState.wagerId}/accept`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                acceptor_wallet: acceptWagerState.acceptorWallet,
                deposit_tx_signature: txSignature,
                source: 'web'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            loadingOverlay.remove();
            throw new Error(error.detail || 'Failed to execute coinflip');
        }

        const result = await response.json();

        console.log('✅ Wager accepted successfully:', result);

        // Remove loading overlay before showing animation
        loadingOverlay.remove();

        // Hide modal (don't call closeAcceptModal which would trigger abandon)
        document.getElementById('acceptWagerModal').style.display = 'none';

        // Show result BEFORE clearing state (showGameResult needs the state data!)
        showGameResult(result);

        // Clear accept state to prevent abandon-accept from being called
        // (Do this AFTER showGameResult so it can access the state data)
        acceptWagerState = {
            wagerId: null,
            amount: null,
            creatorSide: null,
            yourSide: null,
            acceptorWallet: null,
            escrowAddress: null,
            depositAmount: null
        };

        // Refresh wagers list and user stats
        loadActiveWagers();
        await checkSession();

    } catch (err) {
        console.error('❌ Error executing wager:', err);
        console.error('Error details:', err.message, err.stack);
        alert(err.message || 'Failed to execute coinflip. Please contact support.');

        // Remove loading overlay if it exists
        const overlay = document.getElementById('verifyingOverlay');
        if (overlay) overlay.remove();
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

// OLD FUNCTION - REPLACED BY AUTO DEPOSIT MONITORING
// Kept for reference, can be deleted in next cleanup

function showGameResult(result) {
    const isWinner = result.winner_wallet === acceptWagerState.acceptorWallet;
    const payout = (acceptWagerState.amount * 2) * 0.98;

    // Determine which animation to play
    const animationFile = result.result === 'heads'
        ? 'animations/Coin Flip Animation.mp4'
        : 'animations/Coin Flip Animation Kek God.mp4';

    console.log('🎬 ANIMATION START - File:', animationFile);

    // Store result data first
    window.pendingGameResult = {
        isWinner,
        result: result.result,
        yourSide: acceptWagerState.yourSide,
        payout,
        amount: acceptWagerState.amount,
        blockhash: result.blockhash
    };

    // Create a fullscreen overlay for the animation (CANNOT BE MISSED)
    const overlay = document.createElement('div');
    overlay.id = 'animationOverlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0, 0, 0, 0.95);
        z-index: 999999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
    `;

    overlay.innerHTML = `
        <h2 style="color: #FFD700; font-size: 2rem; margin-bottom: 20px; text-align: center;">
            🪙 FLIPPING THE COIN...
        </h2>
        <video id="coinFlipVideo" autoplay playsinline
               style="max-width: 90%; max-height: 70vh; width: auto; height: auto; border-radius: 12px; box-shadow: 0 0 50px rgba(20, 241, 149, 0.5);">
            <source src="${animationFile}" type="video/mp4">
            Your browser does not support video playback.
        </video>
        <div style="margin-top: 30px;">
            <button onclick="skipAnimation()"
                    style="padding: 15px 40px; font-size: 1.3rem; background: #14F195; color: #000; border: none; border-radius: 12px; cursor: pointer; font-weight: bold; box-shadow: 0 4px 20px rgba(20, 241, 149, 0.4);">
                SKIP ANIMATION →
            </button>
        </div>
        <p id="videoStatus" style="color: #FFD700; margin-top: 20px; font-size: 1.2rem; font-weight: bold;">
            INITIALIZING...
        </p>
    `;

    document.body.appendChild(overlay);
    console.log('🎬 Overlay created and added to body');

    // Get video element immediately (no setTimeout)
    const video = document.getElementById('coinFlipVideo');
    const status = document.getElementById('videoStatus');

    console.log('🎬 Video element:', video ? 'FOUND' : 'NOT FOUND');

    if (!video) {
        alert('ERROR: Video element not found!');
        showFinalResult();
        return;
    }

    status.textContent = `LOADING: ${animationFile.split('/').pop()}`;

    // Immediate event listeners
    video.addEventListener('loadstart', () => {
        console.log('🎬 VIDEO LOADING STARTED');
        status.textContent = 'LOADING VIDEO...';
    });

    video.addEventListener('loadeddata', () => {
        console.log('🎬 VIDEO LOADED - Duration:', video.duration, 'seconds');
        status.textContent = `PLAYING... (${video.duration.toFixed(1)}s)`;
    });

    video.addEventListener('playing', () => {
        console.log('🎬 VIDEO IS PLAYING NOW');
        status.textContent = 'ANIMATION PLAYING...';
    });

    video.addEventListener('ended', () => {
        console.log('🎬 VIDEO ENDED');
        const overlay = document.getElementById('animationOverlay');
        if (overlay) overlay.remove();
        showFinalResult();
    });

    video.addEventListener('error', (e) => {
        console.error('🎬 VIDEO ERROR:', e, video.error);
        alert('VIDEO ERROR: ' + (video.error ? video.error.message : 'Unknown'));
        const overlay = document.getElementById('animationOverlay');
        if (overlay) overlay.remove();
        showFinalResult();
    });

    console.log('🎬 Event listeners attached, video should start playing');
}

function skipAnimation() {
    console.log('🎬 SKIP ANIMATION clicked');
    const overlay = document.getElementById('animationOverlay');
    if (overlay) {
        overlay.remove();
        console.log('🎬 Overlay removed');
    }
    showFinalResult();
}

function showFinalResult() {
    console.log('🎬 SHOWING FINAL RESULT');

    const resultContainer = document.getElementById('gameResultContent');
    const data = window.pendingGameResult;

    if (!data) {
        console.error('🎬 ERROR: No pending game result data!');
        return;
    }

    console.log('🎬 Result data:', data);

    // Re-show the modal and switch to step 3 (result display)
    const modal = document.getElementById('acceptWagerModal');
    modal.style.display = 'flex';  // Re-show the modal that was hidden
    document.getElementById('acceptStep1').style.display = 'none';
    document.getElementById('acceptStep2').style.display = 'none';
    document.getElementById('acceptStep3').style.display = 'block';

    // Reset modal size
    const modalContent = modal.querySelector('.modal-content');
    if (modalContent) {
        modalContent.style.maxWidth = '500px';
    }

    let html = '';

    if (data.isWinner) {
        html = `
            <div class="result-icon win-icon">WIN</div>
            <h2 class="result-title win">YOU WON!</h2>
            <div class="result-details">
                <div class="result-row">
                    <span>Coin Result:</span>
                    <span>${data.result.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Your Side:</span>
                    <span>${data.yourSide.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Payout:</span>
                    <span style="color: var(--success); font-weight: 700;">${data.payout.toFixed(4)} SOL</span>
                </div>
            </div>
            <p class="fairness-note">
                Provably Fair<br>
                <small>Blockhash: ${data.blockhash ? data.blockhash.slice(0, 20) + '...' : 'N/A'}</small>
            </p>
        `;
    } else {
        html = `
            <div class="result-icon lose-icon">LOSS</div>
            <h2 class="result-title lose">YOU LOST</h2>
            <div class="result-details">
                <div class="result-row">
                    <span>Coin Result:</span>
                    <span>${data.result.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Your Side:</span>
                    <span>${data.yourSide.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Lost:</span>
                    <span style="color: var(--danger); font-weight: 700;">${data.amount} SOL</span>
                </div>
            </div>
            <p class="fairness-note">
                Provably Fair<br>
                <small>Blockhash: ${data.blockhash ? data.blockhash.slice(0, 20) + '...' : 'N/A'}</small>
            </p>
        `;
    }

    resultContainer.innerHTML = html;
    window.pendingGameResult = null;
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
            const winnerShort = game.winner_username ||
                (game.winner_wallet ? `${game.winner_wallet.slice(0, 4)}...${game.winner_wallet.slice(-4)}` : 'N/A');
            const payout = (game.amount * 2 * 0.98).toFixed(4);
            const timeAgo = getTimeAgo(new Date(game.completed_at));
            const blockhashShort = game.proof && game.proof.blockhash ?
                `${game.proof.blockhash.slice(0, 12)}...${game.proof.blockhash.slice(-8)}` : 'N/A';

            return `
                <div class="recent-game-card" onclick="showProofModal('${game.game_id}', ${JSON.stringify(game.proof).replace(/"/g, '&quot;')}, '${game.payout_tx || ''}')">
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

function showProofModal(gameId, proof, payoutTx) {
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

            ${payoutTx ? `<a href="https://solscan.io/tx/${payoutTx}" target="_blank" class="btn btn-secondary">
                View Payout on Solscan
            </a>` : ''}
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
    const accountInfoDiv = document.getElementById('supportAccountInfo');
    const statusEl = document.getElementById('supportStatus');

    // Password reset is special - users who forgot password can't log in
    const isPasswordReset = ticketType === 'password_reset';

    // REQUIRE LOGIN for non-password-reset support
    if (!isPasswordReset && (!currentUser || !currentUser.email)) {
        alert('Please log in to contact support.');
        showLoginModal();
        return;
    }

    // Reset form
    document.getElementById('supportForm').reset();
    statusEl.style.display = 'none';

    // Set type based on parameter
    typeSelect.value = ticketType;

    // Set title and content based on type
    if (isPasswordReset) {
        titleEl.textContent = 'Password Reset Request';
        subjectInput.value = 'Password Reset Request';
        messageInput.placeholder = 'Any additional info (optional)...';

        // For password reset - ask for email (they know their account email)
        accountInfoDiv.innerHTML = `
            <label style="color: var(--text-muted); margin-bottom: 8px; display: block;">Email associated with your account</label>
            <input type="email" id="supportEmail" class="form-input" placeholder="your@email.com" required>
        `;
        accountInfoDiv.style.display = 'block';
    } else {
        titleEl.textContent = 'Contact Support';
        subjectInput.value = '';
        messageInput.placeholder = 'Describe your issue in detail...';

        // Auto-fill from logged in user (readonly display)
        accountInfoDiv.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: var(--text-muted);">Username:</span>
                <span style="font-weight: 600;">${currentUser.username || currentUser.display_name || 'N/A'}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: var(--text-muted);">Email:</span>
                <span style="font-weight: 600;">${currentUser.email}</span>
            </div>
            <input type="hidden" id="supportEmail" value="${currentUser.email}">
        `;
        accountInfoDiv.style.display = 'block';
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
