function amountOf(value) {
  const n = Number.parseFloat(String(value ?? '').replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}

/** Ledger truth for "זמין למשיכה": completed (released) sales net of platform fees. */
export function availableFundsFromTransactions(transactions) {
  return (transactions || [])
    .filter((tx) => tx?.display_status === 'available')
    .reduce((sum, tx) => sum + amountOf(tx.net_earnings), 0);
}

export function pendingFundsFromTransactions(transactions) {
  return (transactions || [])
    .filter((tx) => tx?.display_status === 'pending_event')
    .reduce((sum, tx) => sum + amountOf(tx.net_earnings), 0);
}
