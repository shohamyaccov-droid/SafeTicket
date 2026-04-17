import { Link, useSearchParams } from 'react-router-dom';

export default function PaymeCheckoutFailure() {
  const [searchParams] = useSearchParams();
  const orderIdRaw = searchParams.get('order_id');

  return (
    <div className="page-shell" style={{ maxWidth: 560, margin: '3rem auto', padding: '0 1rem', direction: 'rtl', textAlign: 'center' }}>
      <h1 style={{ marginBottom: '1rem' }}>התשלום לא הושלם</h1>
      {orderIdRaw && (
        <p style={{ color: '#64748b', marginBottom: '1rem' }}>
          מספר הזמנה: <strong>{orderIdRaw}</strong>
        </p>
      )}
      <p style={{ marginBottom: '1.5rem', lineHeight: 1.6 }}>
        העסקה ב-Payme לא אושרה או בוטלה. לא בוצע חיוב סופי. ניתן לחזור לרשימת הכרטיסים ולנסות שוב.
      </p>
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
        <Link to="/" style={{ fontWeight: 600 }}>
          לדף הבית
        </Link>
        <Link to="/dashboard" style={{ fontWeight: 600 }}>
          לאזור האישי
        </Link>
      </div>
    </div>
  );
}
