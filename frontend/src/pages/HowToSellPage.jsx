import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import JsonLdScript from '../components/JsonLdScript';
import {
  HOW_TO_SELL,
  buildHowToSellFaqJsonLd,
  buildHowToSellHowToJsonLd,
} from '../content/howToSellContent';
import { staticPageBreadcrumbs } from '../content/staticPageMeta';
import './HowToSellPage.css';

/**
 * SGE landing for "איך למכור כרטיס להופעה" / "נתקעתי עם כרטיס".
 * AppChrome already wraps routes in <main> — do not nest another <main>.
 */
const HowToSellPage = () => {
  useEffect(() => {
    document.title = HOW_TO_SELL.title;
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.setAttribute('name', 'description');
      document.head.appendChild(meta);
    }
    meta.setAttribute('content', HOW_TO_SELL.description);
    document.body.classList.add('has-how-to-sell-cta');
    return () => document.body.classList.remove('has-how-to-sell-cta');
  }, []);

  return (
    <article className="how-to-sell" dir="rtl">
      <PageSeo
        title={HOW_TO_SELL.title}
        description={HOW_TO_SELL.description}
        path={HOW_TO_SELL.path}
        jsonLd={buildHowToSellFaqJsonLd(HOW_TO_SELL)}
        breadcrumbs={staticPageBreadcrumbs('/how-to-sell')}
      />
      <JsonLdScript id="how-to-sell-howto-jsonld" data={buildHowToSellHowToJsonLd(HOW_TO_SELL)} />

      <header className="how-to-sell__header">
        <h1 id="how-to-sell-h1">{HOW_TO_SELL.h1}</h1>
        <p className="how-to-sell__intro">{HOW_TO_SELL.intro}</p>
        <p className="how-to-sell__inline-cta how-to-sell__inline-cta--hero">
          <Link className="how-to-sell__button" to={HOW_TO_SELL.cta_path}>
            {HOW_TO_SELL.cta_label}
          </Link>
        </p>
      </header>

      <section className="how-to-sell__steps" aria-labelledby="how-to-sell-steps">
        <h2 id="how-to-sell-steps">{HOW_TO_SELL.steps_h2}</h2>
        <p>{HOW_TO_SELL.steps_lead}</p>
        <ol>
          {HOW_TO_SELL.steps.map((step) => (
            <li key={step.name}>
              <strong>{step.name}</strong>
              <span>{step.text}</span>
            </li>
          ))}
        </ol>
      </section>

      {HOW_TO_SELL.faqs.map((item) => (
        <section key={item.question}>
          <h2>{item.question}</h2>
          <p>{item.answer}</p>
        </section>
      ))}

      <p className="how-to-sell__inline-cta">
        <Link className="how-to-sell__button" to={HOW_TO_SELL.cta_path}>
          {HOW_TO_SELL.cta_label}
        </Link>
      </p>

      <aside className="how-to-sell__sticky" aria-label="מכירת כרטיס">
        <Link className="how-to-sell__button how-to-sell__button--sticky" to={HOW_TO_SELL.cta_path}>
          {HOW_TO_SELL.cta_label}
        </Link>
      </aside>
    </article>
  );
};

export default HowToSellPage;
