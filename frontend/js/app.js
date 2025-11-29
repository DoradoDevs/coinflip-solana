/**
 * Coinflip - PVP Solana Wagers
 * Escrow-based system - No wallet connection required
 */

// API Configuration
const API_BASE = 'https://api.coinflipvp.com';

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
    loadActiveWagers();
    loadRecentGames();
    initializeEventListeners();

    // Refresh wagers every 15 seconds
    setInterval(loadActiveWagers, 15000);

    // Refresh recent games every 30 seconds
    setInterval(loadRecentGames, 30000);
});

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
                creator_side: createWagerState.selectedSide,
                amount: createWagerState.selectedAmount,
                source: 'web'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create wager');
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

        if (!games || games.length === 0) {
            container.innerHTML = '<div class="no-games">No games played yet. Be the first!</div>';
            return;
        }

        container.innerHTML = games.map(game => {
            const winnerShort = game.winner_wallet ?
                `${game.winner_wallet.slice(0, 4)}...${game.winner_wallet.slice(-4)}` : 'N/A';
            const payout = (game.amount * 2 * 0.98).toFixed(4);
            const timeAgo = getTimeAgo(new Date(game.completed_at));

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
    alert(`Provably Fair System

Our coinflip uses Solana's blockhash for true randomness:

1. When you play, we get the latest Solana blockhash
2. We combine: SHA-256(blockhash + game_id)
3. If the first byte is even = HEADS, if odd = TAILS

Why it's fair:
- Blockhash is generated by Solana network
- It's unpredictable and verifiable on-chain
- 128 even values (0,2,4...254) = 50% HEADS
- 128 odd values (1,3,5...255) = 50% TAILS
- Every result can be verified!

All funds are held in escrow until the flip is complete.`);
}
