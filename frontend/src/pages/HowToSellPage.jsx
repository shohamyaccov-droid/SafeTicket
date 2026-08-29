import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import PageSeo from '../components/PageSeo';
import JsonLdScript from '../components/JsonLdScript';
import {
  HOW_TO_SELL,
  buildHowToSellFaqJsonLd,
  buildHowToSellHowToJsonLd,
} from '../content/howToSellContent';
import './HowToSellPage.css';

const HowToSellPage = () => {
  useEffect(() => {
    document.title = HOW_TO_SELL.title;
    document.body.classList.add('has-how-to-sell-cta');
    return () => document.body.classList.remove('has-how-to-sell-cta');
  }, []);

  return (
    <div className="how-to-sell" dir="rtl">
      <PageSeo
        title={HOW_TO_SELL.title}
        description={HOW_TO_SELL.description}
        path={HOW_TO_SELL.path}
        jsonLd={buildHowToSellFaqJsonLd(HOW_TO_SELL)}
      />
      <JsonLdScript id="how-to-sell-howto-jsonld" data={buildHowToSellHowToJsonLd(HOW_TO_SELL)} />

      <article className="how-to-sell__article">
        <h1 id="how-to-sell-h1">{HOW_TO_SELL.h1}</h1>
        <p className="how-to-sell__intro">{HOW_TO_SELL.intro}</p>

        <section className="how-to-sell__steps" aria-labelledby="how-to-sell-steps">
          <h2 id="how-to-sell-steps">{HOW_TO_SELL.steps_h2}</h2>
          <p>{HOW_TO_SELL.steps_lead}</p>
          <ol>
            {HOW_TO_SELL.steps.map((step) => (
              <li key={step.name}>
                <div>
                  <strong>{step.name}</strong>
                  <span>{step.text}</span>
                </div>
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
      </article>

      <div className="how-to-sell__sticky" role="region" aria-label="מכירת כרטיס">
        <Link className="how-to-sell__button how-to-sell__button--sticky" to={HOW_TO_SELL.cta_path}>
          {HOW_TO_SELL.cta_label}
        </Link>
      </div>
    </div>
  );
};

export default HowToSellPage;
