import './CheckoutSecureBadges.css';

export default function CheckoutSecureBadges() {
  return (
    <div className="checkout-secure-badges" dir="rtl">
      <div className="checkout-secure-badges__icons" aria-hidden="true">
        <span className="checkout-secure-badges__lock" title="תשלום מאובטח">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M8 11V8.2C8 5.9 9.8 4 12 4s4 1.9 4 4.2V11"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" strokeWidth="2" />
          </svg>
        </span>
        <svg width="40" height="24" viewBox="0 0 40 24" fill="none">
          <rect width="40" height="24" rx="4" fill="#1434CB" />
          <path d="M16.5 12C16.5 10.5 17.5 9.5 19 9.5C20.5 9.5 21.5 10.5 21.5 12C21.5 13.5 20.5 14.5 19 14.5C17.5 14.5 16.5 13.5 16.5 12Z" fill="white" />
          <path d="M23.5 12C23.5 10.5 24.5 9.5 26 9.5C27.5 9.5 28.5 10.5 28.5 12C28.5 13.5 27.5 14.5 26 14.5C24.5 14.5 23.5 13.5 23.5 12Z" fill="white" />
        </svg>
        <svg width="40" height="24" viewBox="0 0 40 24" fill="none">
          <rect width="40" height="24" rx="4" fill="#EB001B" />
          <circle cx="15" cy="12" r="6" fill="#F79E1B" />
          <circle cx="25" cy="12" r="6" fill="#FF5F00" />
        </svg>
        <span className="checkout-secure-badges__payme">PayMe</span>
      </div>
      <p className="checkout-secure-badges__copy">
        הסליקה מאובטחת. פרטי האשראי אינם נשמרים במערכת.
      </p>
    </div>
  );
}
