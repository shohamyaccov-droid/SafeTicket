import howItWorks from './how-it-works.json';
import { buildHowItWorksCrawlerHtml, buildHowToJsonLd } from './howItWorksRender';

export const HOW_IT_WORKS = howItWorks;
export const HOW_IT_WORKS_DOCUMENT_TITLE = howItWorks.h1;
export { buildHowItWorksCrawlerHtml, buildHowToJsonLd };
