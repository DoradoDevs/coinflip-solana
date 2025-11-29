/**
 * Solana Coinflip - Main Application
 * PVP Wager System
 */

// API Configuration
const API_BASE = 'https://api.coinflipvp.com';
const API_URL = API_BASE;

// Global state
let wallet = null;
let gameState = {
    selectedSide: null,
    selectedAmount: null,
    currentWager: null,
};

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    initializeWallet();
    initializeEventListeners();
    startWebSocket();
});

/**
 * Initialize Phantom Wallet
 */
function initializeWallet() {
    wallet = new PhantomWallet();

    // Override callbacks
    wallet.onAccountChange = async (newAddress) => {
        await updateWalletUI();
        await loadUserStats();
    };

    wallet.onDisconnect = () => {
        updateWalletUI();
        showGameModeSection();
    };
}

/**
 * Initialize Event Listeners
 */
function initializeEventListeners() {
    // Wallet connection
    document.getElementById('connectWallet').addEventListener('click', connectWallet);

    // Game mode selection
    document.getElementById('quickFlipMode').addEventListener('click', () => {
        if (!wallet.connected) {
            alert('Please connect your wallet first!');
            return;
        }
        showQuickFlipSection();
    });

    document.getElementById('pvpMode').addEventListener('click', () => {
        alert('PVP Mode: Create and accept wagers from other players!');
        if (wallet.connected) {
            showQuickFlipSection(); // For now, use same UI
        }
    });

    // Navigation
    document.getElementById('backToModes').addEventListener('click', showGameModeSection);
    document.getElementById('backToModesFromResult').addEventListener('click', showGameModeSection);

    // Coin selection
    document.querySelectorAll('.coin-btn').forEach(btn => {
        btn.addEventListener('click', () => selectSide(btn.dataset.side));
    });

    // Amount selection
    document.querySelectorAll('.amount-btn').forEach(btn => {
        btn.addEventListener('click', () => selectAmount(parseFloat(btn.dataset.amount)));
    });

    document.getElementById('useCustomAmount').addEventListener('click', () => {
        const amount = parseFloat(document.getElementById('customAmount').value);
        if (amount > 0) {
            selectAmount(amount);
        } else {
            alert('Please enter a valid amount');
        }
    });

    // Play button
    document.getElementById('playButton').addEventListener('click', playGame);
    document.getElementById('playAgain').addEventListener('click', resetGame);

    // Modal
    document.querySelector('.modal-close').addEventListener('click', closeModal);
    document.getElementById('showHelp').addEventListener('click', showHelpModal);
    document.getElementById('showFairness').addEventListener('click', showFairnessModal);
}

/**
 * Connect Wallet
 */
async function connectWallet() {
    const connected = await wallet.connect();

    if (connected) {
        await updateWalletUI();
        await connectUser();
        await loadUserStats();
    }
}

/**
 * Update Wallet UI
 */
async function updateWalletUI() {
    const connectBtn = document.getElementById('connectWallet');
    const walletInfo = document.getElementById('walletInfo');
    const walletAddress = document.getElementById('walletAddress');
    const walletBalance = document.getElementById('walletBalance');

    if (wallet.connected) {
        const address = wallet.getAddress();
        const balance = await wallet.getBalance();

        connectBtn.style.display = 'none';
        walletInfo.style.display = 'flex';
        walletAddress.textContent = `${address.slice(0, 4)}...${address.slice(-4)}`;
        walletBalance.textContent = `${balance.toFixed(4)} SOL`;
    } else {
        connectBtn.style.display = 'block';
        walletInfo.style.display = 'none';
    }
}

/**
 * Connect user to backend
 */
async function connectUser() {
    try {
        const response = await fetch(`${API_URL}/user/connect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ wallet_address: wallet.getAddress() })
        });

        const data = await response.json();
        console.log('User connected:', data);
    } catch (err) {
        console.error('Error connecting user:', err);
    }
}

/**
 * Load User Statistics
 */
async function loadUserStats() {
    if (!wallet.connected) return;

    try {
        const response = await fetch(`${API_URL}/user/${wallet.getAddress()}`);
        const data = await response.json();

        document.getElementById('gamesPlayed').textContent = data.games_played;
        document.getElementById('winRate').textContent = data.win_rate;
        document.getElementById('totalWagered').textContent = `${data.total_wagered.toFixed(4)} SOL`;

        const netPL = data.total_won - data.total_lost;
        const netPLElement = document.getElementById('netPL');
        netPLElement.textContent = `${Math.abs(netPL).toFixed(4)} SOL`;
        netPLElement.style.color = netPL >= 0 ? 'var(--success)' : 'var(--danger)';
    } catch (err) {
        console.error('Error loading stats:', err);
    }
}

/**
 * Section Navigation
 */
function showGameModeSection() {
    document.getElementById('gameModeSection').style.display = 'block';
    document.getElementById('quickFlipSection').style.display = 'none';
    resetGame();
}

function showQuickFlipSection() {
    document.getElementById('gameModeSection').style.display = 'none';
    document.getElementById('quickFlipSection').style.display = 'block';
    resetGame();
}

/**
 * Reset Game
 */
function resetGame() {
    gameState = {
        selectedSide: null,
        selectedAmount: null,
        currentWager: null,
    };

    // Reset UI
    document.querySelectorAll('.coin-btn').forEach(btn => btn.classList.remove('selected'));
    document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
    document.getElementById('customAmount').value = '';

    // Show first step
    document.getElementById('chooseSide').style.display = 'block';
    document.getElementById('chooseAmount').style.display = 'none';
    document.getElementById('confirmGame').style.display = 'none';
    document.getElementById('flipping').style.display = 'none';
    document.getElementById('gameResult').style.display = 'none';
}

/**
 * Select Coin Side
 */
function selectSide(side) {
    gameState.selectedSide = side;

    // Update UI
    document.querySelectorAll('.coin-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.side === side);
    });

    // Show next step
    setTimeout(() => {
        document.getElementById('chooseSide').style.display = 'none';
        document.getElementById('chooseAmount').style.display = 'block';
    }, 300);
}

/**
 * Select Amount
 */
function selectAmount(amount) {
    gameState.selectedAmount = amount;

    // Update UI
    document.querySelectorAll('.amount-btn').forEach(btn => {
        btn.classList.toggle('selected', parseFloat(btn.dataset.amount) === amount);
    });

    // Show confirmation
    setTimeout(() => {
        showConfirmation();
    }, 300);
}

/**
 * Show Confirmation
 */
function showConfirmation() {
    const sideEmoji = gameState.selectedSide === 'heads' ? '🪙' : '🎯';
    const potentialWin = (gameState.selectedAmount * 2) * 0.98; // 2% fee

    document.getElementById('selectedSide').innerHTML = `${sideEmoji} ${gameState.selectedSide.toUpperCase()}`;
    document.getElementById('selectedAmount').textContent = `${gameState.selectedAmount} SOL`;
    document.getElementById('potentialWin').textContent = `${potentialWin.toFixed(4)} SOL`;

    document.getElementById('chooseAmount').style.display = 'none';
    document.getElementById('confirmGame').style.display = 'block';
}

/**
 * Play Game
 */
async function playGame() {
    // Show flipping animation
    document.getElementById('confirmGame').style.display = 'none';
    document.getElementById('flipping').style.display = 'block';

    try {
        // Call API to play game
        const response = await fetch(`${API_URL}/game/quick-flip`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                wallet_address: wallet.getAddress(),
                side: gameState.selectedSide,
                amount: gameState.selectedAmount
            })
        });

        if (!response.ok) {
            throw new Error('Game failed');
        }

        const gameResult = await response.json();

        // Wait for animation
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Show result
        showResult(gameResult);

        // Update stats
        await loadUserStats();
        await updateWalletUI();

    } catch (err) {
        console.error('Error playing game:', err);
        alert('Game failed! Please try again.');
        resetGame();
    }
}

/**
 * Show Game Result
 */
function showResult(gameResult) {
    const won = gameResult.winner_wallet === wallet.getAddress();
    const resultEmoji = gameResult.result === 'heads' ? '🪙' : '🎯';

    let resultHTML = '';

    if (won) {
        const payout = (gameResult.amount * 2) * 0.98;
        resultHTML = `
            <div class="result-icon">🎉</div>
            <div class="result-title win">YOU WON!</div>
            <div class="result-details">
                <div class="result-row">
                    <span>Result:</span>
                    <span>${resultEmoji} ${gameResult.result.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Wager:</span>
                    <span>${gameResult.amount} SOL</span>
                </div>
                <div class="result-row">
                    <span>Won:</span>
                    <span style="color: var(--success); font-weight: 700;">${payout.toFixed(4)} SOL</span>
                </div>
            </div>
            <p style="margin-top: 20px; color: var(--text-muted); font-size: 0.9rem;">
                🔍 Provably Fair<br>
                Blockhash: <code>${gameResult.blockhash ? gameResult.blockhash.slice(0, 16) + '...' : 'N/A'}</code>
            </p>
        `;
    } else {
        resultHTML = `
            <div class="result-icon">😔</div>
            <div class="result-title lose">YOU LOST</div>
            <div class="result-details">
                <div class="result-row">
                    <span>Result:</span>
                    <span>${resultEmoji} ${gameResult.result.toUpperCase()}</span>
                </div>
                <div class="result-row">
                    <span>Lost:</span>
                    <span style="color: var(--danger); font-weight: 700;">${gameResult.amount} SOL</span>
                </div>
            </div>
            <p style="margin-top: 20px; color: var(--text-muted); font-size: 0.9rem;">
                🔍 Provably Fair<br>
                Blockhash: <code>${gameResult.blockhash ? gameResult.blockhash.slice(0, 16) + '...' : 'N/A'}</code>
            </p>
        `;
    }

    document.getElementById('resultContent').innerHTML = resultHTML;
    document.getElementById('flipping').style.display = 'none';
    document.getElementById('gameResult').style.display = 'block';
}

/**
 * WebSocket for Live Updates
 */
function startWebSocket() {
    // const ws = new WebSocket(`ws://${window.location.host}/ws`);

    // ws.onmessage = (event) => {
    //     const data = JSON.parse(event.data);
    //     console.log('WebSocket message:', data);
    //     // Handle live updates (new wagers, game results, etc.)
    // };

    // ws.onerror = (error) => {
    //     console.error('WebSocket error:', error);
    // };
}

/**
 * Modals
 */
function showHelpModal() {
    const helpContent = `
        <h2>❓ How to Play</h2>
        <p><strong>Solana Coinflip</strong> is a provably fair PVP coinflip game.</p>
        <h3>Game Modes:</h3>
        <ul>
            <li><strong>Quick Flip:</strong> Instant game vs house</li>
            <li><strong>PVP Wager:</strong> Create/accept player challenges</li>
        </ul>
        <h3>How It Works:</h3>
        <ol>
            <li>Connect your Phantom wallet</li>
            <li>Choose heads or tails</li>
            <li>Select your wager amount</li>
            <li>Coin flips using Solana blockhash (provably fair)</li>
            <li>Winner gets 2x wager minus 2% fee</li>
        </ol>
        <h3>Fairness:</h3>
        <p>All flips use Solana blockhash for true randomness. Every game can be verified!</p>
    `;

    showModal(helpContent);
}

function showFairnessModal() {
    const fairnessContent = `
        <h2>🔍 Provably Fair System</h2>
        <p>Our coinflip game uses Solana's blockhash for true randomness.</p>
        <h3>How It Works:</h3>
        <ol>
            <li>When you play, we fetch the latest Solana blockhash</li>
            <li>We combine: SHA-256(blockhash + game_id)</li>
            <li>If the hash is even → HEADS, if odd → TAILS</li>
        </ol>
        <h3>Why This Is Fair:</h3>
        <ul>
            <li>Blockhash is generated by Solana network (not us!)</li>
            <li>It's unpredictable and verifiable on-chain</li>
            <li>You can verify every game result yourself</li>
        </ul>
        <p>Every game shows the blockhash used. Check it on Solana explorer!</p>
    `;

    showModal(fairnessContent);
}

function showModal(content) {
    document.getElementById('modalBody').innerHTML = content;
    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

// Close modal on outside click
window.onclick = (event) => {
    const modal = document.getElementById('modal');
    if (event.target === modal) {
        closeModal();
    }
};
