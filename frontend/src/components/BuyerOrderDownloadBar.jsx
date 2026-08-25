/* eslint-disable react/prop-types */
import {
  isPaidActiveOrder,
  orderTicketIds,
  orderTicketIsDownloadable,
  resolveDownloadTicketId,
} from '../utils/buyerOrderActions';

function DownloadIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function BuyerOrderDownloadBar({ purchase, onDownload }) {
  if (!isPaidActiveOrder(purchase)) return null;

  const tickets = Array.isArray(purchase?.tickets) ? purchase.tickets : [];
  const ticketIds = orderTicketIds(purchase);
  const anyFlagged = tickets.some(orderTicketIsDownloadable);

  const handleDownload = (explicitId) => {
    const id = explicitId ?? resolveDownloadTicketId(purchase);
    onDownload?.(id);
  };

  if (ticketIds.length > 1) {
    const ids = tickets.length === ticketIds.length ? tickets.map((t) => t.id) : ticketIds;
    return (
      <div className="buyer-order-download-bar" data-testid="buyer-order-download-bar">
        <div className="multi-download-buttons">
          {ids.map((id, idx) => {
            const ticket = tickets[idx];
            const disabled = anyFlagged && ticket ? !orderTicketIsDownloadable(ticket) : false;
            return (
              <button
                key={id ?? `ticket-${idx}`}
                type="button"
                onClick={() => handleDownload(id)}
                className="primary-button download-button buyer-download-ticket-btn"
                disabled={disabled}
              >
                <DownloadIcon />
                הורד כרטיס {idx + 1}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="buyer-order-download-bar" data-testid="buyer-order-download-bar">
      <button
        type="button"
        onClick={() => handleDownload(ticketIds[0])}
        className="primary-button download-button buyer-download-ticket-btn"
      >
        <DownloadIcon />
        הורד כרטיס
      </button>
    </div>
  );
}
