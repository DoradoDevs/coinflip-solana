/**
 * Phantom Wallet Integration for Solana Coinflip
 */

class PhantomWallet {
    constructor() {
        this.provider = null;
        this.publicKey = null;
        this.connected = false;
    }

    /**
     * Check if Phantom is installed
     */
    isPhantomInstalled() {
        const isPhantom = window.solana && window.solana.isPhantom;
        return Boolean(isPhantom);
    }

    /**
     * Connect to Phantom wallet
     */
    async connect() {
        if (!this.isPhantomInstalled()) {
            alert('Phantom wallet is not installed! Please install it from https://phantom.app');
            window.open('https://phantom.app', '_blank');
            return false;
        }

        try {
            const resp = await window.solana.connect();
            this.provider = window.solana;
            this.publicKey = resp.publicKey.toString();
            this.connected = true;

            console.log('Connected to wallet:', this.publicKey);

            // Listen for account changes
            window.solana.on('accountChanged', (publicKey) => {
                if (publicKey) {
                    this.publicKey = publicKey.toString();
                    this.onAccountChange(this.publicKey);
                } else {
                    this.disconnect();
                }
            });

            // Listen for disconnect
            window.solana.on('disconnect', () => {
                this.disconnect();
            });

            return true;
        } catch (err) {
            console.error('Error connecting to Phantom:', err);
            return false;
        }
    }

    /**
     * Disconnect wallet
     */
    async disconnect() {
        if (this.provider) {
            await this.provider.disconnect();
        }
        this.provider = null;
        this.publicKey = null;
        this.connected = false;
        this.onDisconnect();
    }

    /**
     * Get wallet address
     */
    getAddress() {
        return this.publicKey;
    }

    /**
     * Get wallet balance (SOL)
     */
    async getBalance() {
        if (!this.connected || !this.publicKey) {
            return 0;
        }

        try {
            // Use Solana web3.js if available, or fetch from API
            const response = await fetch(`/api/user/${this.publicKey}/balance`);
            const data = await response.json();
            return data.balance || 0;
        } catch (err) {
            console.error('Error getting balance:', err);
            return 0;
        }
    }

    /**
     * Sign and send transaction
     */
    async signAndSendTransaction(transaction) {
        if (!this.connected) {
            throw new Error('Wallet not connected');
        }

        try {
            const { signature } = await this.provider.signAndSendTransaction(transaction);
            return signature;
        } catch (err) {
            console.error('Error signing transaction:', err);
            throw err;
        }
    }

    /**
     * Sign message (for authentication)
     */
    async signMessage(message) {
        if (!this.connected) {
            throw new Error('Wallet not connected');
        }

        try {
            const encodedMessage = new TextEncoder().encode(message);
            const signature = await this.provider.signMessage(encodedMessage, 'utf8');
            return signature;
        } catch (err) {
            console.error('Error signing message:', err);
            throw err;
        }
    }

    /**
     * Callbacks (to be overridden)
     */
    onAccountChange(newAddress) {
        console.log('Account changed to:', newAddress);
        // Override this in main app
    }

    onDisconnect() {
        console.log('Wallet disconnected');
        // Override this in main app
    }
}

// Export for use in main app
window.PhantomWallet = PhantomWallet;
