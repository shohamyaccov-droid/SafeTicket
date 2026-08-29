import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import {
  HOW_IT_WORKS,
  HOW_IT_WORKS_DOCUMENT_TITLE,
  buildHowToJsonLd,
} from '../content/howItWorksContent';
import './Terms.css';

const HowItWorksPage = () => {
  return (
    <div className="terms-container">
      <PageSeo
        title={HOW_IT_WORKS_DOCUMENT_TITLE}
        description={HOW_IT_WORKS.description}
        path={HOW_IT_WORKS.path}
        jsonLd={buildHowToJsonLd(HOW_IT_WORKS)}
      />
      <article className="terms-card how-it-works-card">
        <h1>{HOW_IT_WORKS.h1}</h1>
        <p>{HOW_IT_WORKS.intro}</p>

        {HOW_IT_WORKS.sections.map((section) => {
          const ListTag = section.list === 'ul' ? 'ul' : 'ol';
          return (
            <section key={section.id}>
              <h2>{section.h2}</h2>
              {section.lead ? <p>{section.lead}</p> : null}
              <ListTag>
                {section.items.map((item) => (
                  <li key={item.strong}>
                    <strong>{item.strong}</strong> {item.text}
                  </li>
                ))}
              </ListTag>
            </section>
          );
        })}

        <p className="how-it-works-cta">
          מוכנים להתחיל?{' '}
          <Link to="/how-to-sell">איך למכור כרטיס להופעה</Link>
          {' · '}
          <Link to="/sell/new">מכירת כרטיס שקניתי</Link>
          {' · '}
          <Link to="/">קניית כרטיסים יד שניה</Link>
          {' · '}
          <Link to="/faq">שאלות ותשובות</Link>
        </p>
      </article>
    </div>
  );
};

export default HowItWorksPage;
