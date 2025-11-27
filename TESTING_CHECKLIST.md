# 🧪 Solana Coinflip - Testing Checklist

**Status:** ESCROW IMPLEMENTATION COMPLETE - READY FOR TESTING
**Date:** 2025-11-27

---

## 🎯 Critical Testing Priority

Test these flows **FIRST** to verify the new escrow security system:

### 1. ✅ Create Wager with Escrow (Telegram)
**Goal:** Verify creator's escrow wallet is created and funded

**Steps:**
1. Start bot: `/start`
2. Deposit 0.1 SOL to bot wallet
3. Click "⚔️ Create Wager"
4. Choose HEADS
5. Select 0.01 SOL amount
6. Click "✅ Confirm"

**Expected Results:**
- ✅ Bot shows "🔒 Generating secure escrow wallet..."
- ✅ Bot shows "💸 Collecting deposit..."
- ✅ Wager created successfully
- ✅ Message shows: "🔒 Funds secured in escrow: `<address>`"
- ✅ Total 0.035 SOL collected (0.01 wager + 0.025 fee)
- ✅ Database: `creator_escrow_address`, `creator_escrow_secret`, `creator_deposit_tx` populated

**Logs to Check:**
```
[ESCROW] Generated unique wallet <address> for wager <id>
[REAL MAINNET] Collected 0.035 SOL from <user_wallet> → escrow <escrow> (tx: <sig>)
[ESCROW] Wallet <address> balance: 0.035 SOL (required: 0.035 SOL)
```

---

### 2. ✅ Accept Wager with Escrow (Telegram)
**Goal:** Verify acceptor's escrow created, game executed with both escrows, and escrows emptied

**Steps:**
1. Use second Telegram account (or second bot instance)
2. Deposit 0.1 SOL
3. Click "🎯 Open Wagers"
4. Find the wager from Test #1
5. Click "Accept"

**Expected Results:**
- ✅ Bot shows "🔒 Creating your escrow..."
- ✅ Bot shows "💸 Collecting deposit..."
- ✅ Bot shows "⚔️ Escrows secured! 🎲 Flipping coin..."
- ✅ Game completes, winner receives payout
- ✅ Both creator and acceptor notified
- ✅ Database: `acceptor_escrow_address`, `acceptor_escrow_secret`, `acceptor_deposit_tx` populated
- ✅ Game record created with winner, blockhash, transactions

**Logs to Check:**
```
[ESCROW] Acceptor <user_id> accepting wager <id>, creating escrow...
[ESCROW] Acceptor escrow created: <address>
[ESCROW GAME] Starting PVP game with escrows: creator=<addr1>, acceptor=<addr2>
[ESCROW GAME] Coin flip result: <HEADS/TAILS>
[ESCROW GAME] Paid winner <amount> SOL (tx: <sig>)
[ESCROW GAME] Collected fees from both escrows (winner: <tx1>, loser: <tx2>)
[ESCROW GAME] Game <id> completed - winner: <user_id>
```

**Critical Verification:**
1. Check escrow balances on Solscan - should be ~0 SOL (rent-exempt minimum)
2. Winner received correct payout (98% of pot)
3. House wallet received all fees from both escrows
4. Both escrow wallets exist but are empty

---

### 3. ✅ Cancel Wager with Refund (Telegram)
**Goal:** Verify wager refunded to creator, fee kept by house

**Steps:**
1. Create another wager (0.01 SOL, HEADS)
2. Wait for escrow creation
3. Click "🎮 My Wagers"
4. Click on your wager
5. Click "❌ Cancel Wager"

**Expected Results:**
- ✅ Bot shows "💸 Processing refund..."
- ✅ Refund message shows:
  - "💰 Refunded: 0.01 SOL"
  - "💳 Fee Kept: 0.025 SOL"
- ✅ Wager status changed to "cancelled"
- ✅ Creator wallet receives 0.01 SOL back
- ✅ House wallet receives 0.025 SOL fee

**Logs to Check:**
```
[CANCEL] Refunding wager <id> from escrow <address>
[REAL MAINNET] Refunded 0.01 SOL to creator (tx: <refund_tx>)
[REAL MAINNET] Collected 0.025 SOL fee to house (tx: <fee_tx>)
```

**Critical Verification:**
1. Check refund transaction on Solscan
2. Check fee collection transaction on Solscan
3. Escrow wallet should have ~0 SOL remaining

---

## 🔒 Security Testing

### 4. ✅ Transaction Signature Reuse Prevention (Web)
**Goal:** Verify same signature cannot be used twice

**Steps:**
1. Create wager via Web API with transaction signature
2. Try to create another wager with the SAME signature
3. Should fail immediately

**Expected Results:**
- ❌ Second attempt fails with: "Transaction signature already used"
- ✅ Database: `used_signatures` table has entry for first wager

---

### 5. ✅ Race Condition Prevention
**Goal:** Verify two users can't accept same wager simultaneously

**Setup:**
- Have two users ready to accept the same wager at almost same time

**Expected Results:**
- ✅ First user: Wager status changes to "accepting" immediately
- ❌ Second user: Gets "This wager is no longer available"
- ✅ Only one game created

---

### 6. ✅ Self-Accept Prevention
**Goal:** Verify user can't accept their own wager

**Steps:**
1. Create wager
2. Try to accept it with same account

**Expected Results:**
- ❌ Error: "You can't accept your own wager!"

---

## 🌐 Cross-Platform Testing

### 7. ✅ Telegram Creates → Web Accepts
**Steps:**
1. Create wager via Telegram bot (0.01 SOL, HEADS)
2. View open wagers via Web API: `GET /api/wagers/open`
3. Accept via Web API: `POST /api/wager/accept` (with deposit signature)

**Expected Results:**
- ✅ Web can see Telegram wager in list
- ✅ Web user's escrow created
- ✅ Game executes correctly
- ✅ Telegram creator gets push notification
- ✅ Both escrows emptied

---

### 8. ✅ Web Creates → Telegram Accepts
**Steps:**
1. Create wager via Web API (with deposit signature)
2. View "🎯 Open Wagers" in Telegram bot
3. Accept via Telegram

**Expected Results:**
- ✅ Telegram bot shows Web wager
- ✅ Telegram user's escrow created
- ✅ Game executes correctly
- ✅ Web user sees update via WebSocket
- ✅ Both escrows emptied

---

## 💰 Balance & Transaction Testing

### 9. ✅ Insufficient Balance
**Steps:**
1. Try to create 0.05 SOL wager with only 0.03 SOL balance

**Expected Results:**
- ❌ Error: "Insufficient balance. Required: 0.075 SOL (0.05 wager + 0.025 fee), Available: 0.03 SOL"

---

### 10. ✅ Verify All Transactions on Solscan
**For every game, verify:**
- ✅ Creator deposit to creator escrow
- ✅ Acceptor deposit to acceptor escrow
- ✅ Winner payout from winner escrow
- ✅ Fee collection from both escrows to house
- ✅ All transactions visible on Solscan with correct amounts

---

## 📊 Database Integrity Testing

### 11. ✅ Database Records Complete
**After each game, verify database has:**

**Wager Record:**
- ✅ `creator_escrow_address` - populated
- ✅ `creator_escrow_secret` - encrypted
- ✅ `creator_deposit_tx` - transaction signature
- ✅ `acceptor_escrow_address` - populated
- ✅ `acceptor_escrow_secret` - encrypted
- ✅ `acceptor_deposit_tx` - transaction signature
- ✅ `status` - "accepted"
- ✅ `game_id` - linked to game

**Game Record:**
- ✅ `game_id` - unique
- ✅ `blockhash` - Solana blockhash used
- ✅ `result` - HEADS or TAILS
- ✅ `winner_id` - correct winner
- ✅ `payout_tx` - transaction signature
- ✅ `status` - "completed"

**Used Signatures:**
- ✅ Both deposit signatures recorded
- ✅ Linked to correct wager_id

---

## 🎮 Edge Cases

### 12. ✅ Cancel Already Accepted Wager
**Steps:**
1. Create wager
2. Someone accepts it
3. Try to cancel (should fail)

**Expected Results:**
- ❌ Error: "This wager can't be cancelled"

---

### 13. ✅ Very Small Amounts
**Test with minimum amounts:**
- ✅ 0.001 SOL wager (check rent-exempt logic)
- ✅ Verify all math correct with tiny amounts

---

### 14. ✅ Multiple Simultaneous Games
**Stress test:**
1. Create 5 wagers simultaneously
2. Accept all 5 from different accounts
3. Verify all games execute correctly
4. Verify all escrows emptied
5. Verify no fund mixing between games

---

## 📝 Testing Workflow

**For each test:**
1. ✅ Execute test steps
2. ✅ Check logs for expected output
3. ✅ Verify transactions on Solscan
4. ✅ Check database records
5. ✅ Verify escrow wallets empty after completion
6. ✅ Document any issues

---

## 🚨 Common Issues to Watch For

**Escrow Issues:**
- [ ] Escrow wallet not created
- [ ] Deposit not collected
- [ ] Escrow balance incorrect
- [ ] Escrow not emptied after game

**Transaction Issues:**
- [ ] Transaction fails with "BlockhashNotFound" (should be fixed with skip_preflight)
- [ ] Transaction signature not recorded
- [ ] Duplicate signature accepted

**Game Logic Issues:**
- [ ] Wrong winner determined
- [ ] Incorrect payout amount
- [ ] Fees not collected properly
- [ ] Stats not updated

**Database Issues:**
- [ ] Escrow fields not populated
- [ ] Used signatures not recorded
- [ ] Wager status not updated

---

## ✅ Testing Complete Checklist

**After all tests pass:**
- [ ] All 14 test scenarios passed
- [ ] All transactions verified on Solscan
- [ ] All database records correct
- [ ] All escrow wallets emptied after games
- [ ] No security vulnerabilities found
- [ ] Cross-platform functionality confirmed
- [ ] Cancel/refund working correctly
- [ ] Logs show all expected output

---

## 🚀 Ready for Production

**Only proceed to production after:**
1. ✅ All critical tests passing (Tests 1-3)
2. ✅ All security tests passing (Tests 4-6)
3. ✅ Cross-platform tests passing (Tests 7-8)
4. ✅ Edge cases handled (Tests 12-14)
5. ✅ Manual verification of transactions on Solscan
6. ✅ Database integrity confirmed

---

## 📞 If Issues Found

**Report with:**
- Test number and description
- Steps to reproduce
- Expected vs actual behavior
- Logs from around the error
- Transaction signatures (if applicable)
- Screenshots/error messages

---

**Good luck testing! 🎲🚀**
