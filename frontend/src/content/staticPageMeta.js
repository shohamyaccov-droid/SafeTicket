import staticPageMeta from './static-page-meta.json';
import { crumbs } from '../utils/breadcrumbSeo';

const CRUMB_NAMES = {
  '/about': 'אודות',
  '/terms': 'תקנון',
  '/privacy': 'פרטיות',
  '/refunds': 'החזרים',
  '/buyer-guarantee': 'הגנת הקונה',
  '/accessibility': 'נגישות',
  '/contact': 'צור קשר',
  '/sell/new': 'מכירת כרטיס',
  '/how-it-works': 'איך זה עובד',
  '/how-to-sell': 'איך למכור כרטיס',
  '/faq': 'שאלות ותשובות',
  '/login': 'התחברות',
  '/register': 'הרשמה',
  '/dashboard': 'האזור האישי',
  '/profile': 'הפרופיל שלי',
};

export function getStaticPageMeta(path) {
  const key = path === '' ? '/' : path.startsWith('/') ? path : `/${path}`;
  return staticPageMeta[key] || null;
}

export function staticPageBreadcrumbs(path, currentName) {
  const key = path === '' ? '/' : path.startsWith('/') ? path : `/${path}`;
  if (key === '/') return [ { name: 'דף הבית', path: '/' } ];
  return crumbs({ name: currentName || CRUMB_NAMES[key] || key, path: key });
}
