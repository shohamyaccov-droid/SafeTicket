import { useState } from 'react';
import { ticketAPI } from '../services/api';
import { toastError, toastSuccess } from '../utils/toast';
import { apiErrorMessageHe } from '../utils/apiErrors';
import { formatAmountForCurrency, currencySymbol, resolveTicketCurrency } from '../utils/priceFormat';
import './SellerTicketActions.css';

/**
 * SellerTicketActions - Displays action buttons for the ticket seller
 * - Change Price: Opens modal to edit listing price
 * - Delete Ticket: Opens confirmation before deleting from marketplace
 */
function DeleteConfirmModal({ isOpen, onConfirm, onCancel, loading }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay-ticket-action" onClick={onCancel}>
      <div
        className="modal-content-ticket-action delete-ticket-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <h3>מחיקת כרטיס</h3>
        <p>האם אתה בטוח שברצונך למחוק את הכרטיס?</p>
        <p className="small-text">לאחר המחיקה, הכרטיס לא יהיה זמין יותר לקונים.</p>
        <div className="modal-actions-ticket">
          <button
            type="button"
            className="modal-btn-cancel"
            onClick={onCancel}
            disabled={loading}
          >
            ביטול
          </button>
          <button
            type="button"
            className="modal-btn-danger"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? 'מחיקה...' : 'מחק כרטיס'}
          </button>
        </div>
      </div>
    </div>
  );
}

function ChangePriceModal({ isOpen, currentPrice, currency, onConfirm, onCancel, loading }) {
  const [newPrice, setNewPrice] = useState(String(currentPrice || ''));
  const currencySymbol_ = currencySymbol(currency || 'ILS');

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    const priceVal = parseFloat(newPrice);
    if (!Number.isFinite(priceVal) || priceVal <= 0) {
      toastError('נא להזין מחיר תקין (מספר חיובי).');
      return;
    }
    onConfirm(priceVal);
  };

  return (
    <div className="modal-overlay-ticket-action" onClick={onCancel}>
      <div
        className="modal-content-ticket-action change-price-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <h3>שינוי מחיר</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group-ticket-action">
            <label htmlFor="newPrice">מחיר חדש</label>
            <div className="price-input-wrapper">
              <span className="currency-symbol">{currencySymbol_}</span>
              <input
                id="newPrice"
                type="number"
                value={newPrice}
                onChange={(e) => setNewPrice(e.target.value)}
                placeholder="הזן מחיר חדש"
                min="0"
                step="0.01"
                autoFocus
                disabled={loading}
                className="price-input-field"
                dir="ltr"
              />
            </div>
          </div>
          <div className="modal-actions-ticket">
            <button
              type="button"
              className="modal-btn-cancel"
              onClick={onCancel}
              disabled={loading}
            >
              ביטול
            </button>
            <button
              type="submit"
              className="modal-btn-confirm"
              disabled={loading || !newPrice}
            >
              {loading ? 'שמירה...' : 'שמור מחיר חדש'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function SellerTicketActions({
  ticket,
  group,
  onPriceChanged,
  onTicketDeleted,
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showChangePrice, setShowChangePrice] = useState(false);
  const [loadingDelete, setLoadingDelete] = useState(false);
  const [loadingPrice, setLoadingPrice] = useState(false);

  if (!ticket || !ticket.id) return null;

  const currency = resolveTicketCurrency(ticket);
  const currentPrice = ticket.asking_price || ticket.original_price || 0;

  const handleDeleteTicket = async () => {
    setLoadingDelete(true);
    try {
      await ticketAPI.deleteTicket(ticket.id);
      toastSuccess('הכרטיס נמחק בהצלחה מהמכירה.');
      setShowDeleteConfirm(false);
      if (onTicketDeleted) {
        onTicketDeleted(ticket.id);
      }
    } catch (err) {
      const msg = apiErrorMessageHe(err, 'שגיאה בעת מחיקת הכרטיס.');
      toastError(msg);
    } finally {
      setLoadingDelete(false);
    }
  };

  const handleChangePrice = async (newPrice) => {
    setLoadingPrice(true);
    try {
      await ticketAPI.updateTicketPrice(ticket.id, newPrice);
      toastSuccess('המחיר עודכן בהצלחה.');
      setShowChangePrice(false);
      if (onPriceChanged) {
        onPriceChanged(ticket.id, newPrice);
      }
    } catch (err) {
      const msg = apiErrorMessageHe(err, 'שגיאה בעת שינוי המחיר.');
      toastError(msg);
    } finally {
      setLoadingPrice(false);
    }
  };

  return (
    <>
      <div className="seller-ticket-actions">
        <button
          type="button"
          className="seller-action-btn seller-action-btn--price"
          onClick={(e) => {
            e.stopPropagation();
            setShowChangePrice(true);
          }}
          title="שנה את מחיר הכרטיס"
          disabled={loadingDelete || loadingPrice}
        >
          <span className="action-icon">✏️</span>
          <span className="action-label">שינוי מחיר</span>
        </button>
        <button
          type="button"
          className="seller-action-btn seller-action-btn--delete"
          onClick={(e) => {
            e.stopPropagation();
            setShowDeleteConfirm(true);
          }}
          title="מחק כרטיס"
          disabled={loadingDelete || loadingPrice}
        >
          <span className="action-icon">🗑</span>
          <span className="action-label">מחיקה</span>
        </button>
      </div>

      <ChangePriceModal
        isOpen={showChangePrice}
        currentPrice={currentPrice}
        currency={currency}
        onConfirm={handleChangePrice}
        onCancel={() => setShowChangePrice(false)}
        loading={loadingPrice}
      />

      <DeleteConfirmModal
        isOpen={showDeleteConfirm}
        onConfirm={handleDeleteTicket}
        onCancel={() => setShowDeleteConfirm(false)}
        loading={loadingDelete}
      />
    </>
  );
}
