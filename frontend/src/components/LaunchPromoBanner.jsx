import { useEffect, useState } from 'react';
import { orderAPI } from '../services/api';
import './LaunchPromoBanner.css';

const FALLBACK = {
  is_active: true,
  bonus_amount: '20.00',
  max_sales: 100,
  remaining_sales: 100,
};

export default function LaunchPromoBanner() {
  const [promo, setPromo] = useState(FALLBACK);

  useEffect(() => {
    let active = true;
    orderAPI
      .getLaunchPromotion()
      .then((response) => {
        if (active && response?.data?.seller_bonus) {
          setPromo(response.data.seller_bonus);
        }
      })
      .catch(() => {
        // Keep the launch message visible during a transient API wake-up.
      });
    return () => {
      active = false;
    };
  }, []);

  if (!promo?.is_active) return null;

  return (
    <aside className="launch-promo-banner" role="status" aria-label="מבצע בונוס למוכרים">
      <span>🎁 20 ₪ בונוס למוכרים! מוגבל ל-100 המכירות הראשונות באתר. קוד קופון: </span>
      <strong>SAFE20</strong>
    </aside>
  );
}
