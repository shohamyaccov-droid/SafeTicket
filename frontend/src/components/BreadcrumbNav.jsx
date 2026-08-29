/* eslint-disable react/prop-types */
import { Link } from 'react-router-dom';
import './BreadcrumbNav.css';

export default function BreadcrumbNav({ items = [], label = 'ניווט היררכי' }) {
  const list = (Array.isArray(items) ? items : []).filter((item) => item?.name);
  if (list.length < 2) return null;
  return (
    <nav className="seo-breadcrumbs" aria-label={label}>
      <ol>
        {list.map((item, index) => {
          const isLast = index === list.length - 1;
          return (
            <li key={`${item.path || item.name}-${index}`}>
              {isLast || !item.path ? (
                <span aria-current={isLast ? 'page' : undefined}>{item.name}</span>
              ) : (
                <Link to={item.path}>{item.name}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
