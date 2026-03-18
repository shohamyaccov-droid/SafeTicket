import { useState } from 'react';
import './FAQ.css';

const FAQ = () => {
  const [openIndex, setOpenIndex] = useState(null);

  const faqs = [
    {
      question: 'האם הרכישה בטוחה?',
      answer: 'כן, 100% בטוח. כל הרכישות מוגנות על ידי מערכת אבטחה מתקדמת ואנו מבטיחים החזר כספי מלא במקרה של בעיה.'
    },
    {
      question: 'מתי אקבל את הכרטיסים?',
      answer: 'בדרך כלל תקבל את הכרטיסים תוך 24 שעות לפני המופע. כרטיסים דיגיטליים יישלחו למייל שלך מיד לאחר הרכישה.'
    },
    {
      question: 'מה קורה אם המופע מבוטל?',
      answer: 'אם המופע מבוטל, תקבל החזר כספי מלא אוטומטית תוך 5-7 ימי עסקים. אין צורך לפנות אלינו - התהליך מתבצע אוטומטית.'
    },
    {
      question: 'איך אני מקבל את הכסף כמוכר?',
      answer: 'כמוכר, תקבל את הכסף בהעברה בנקאית ישירה לחשבון שלך תוך 3-5 ימי עסקים לאחר המופע. כל התשלומים מאובטחים ומנוהלים דרך מערכת מאובטחת.'
    }
  ];

  const toggleFAQ = (index) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <div className="faq-container">
      <div className="faq-header">
        <h1>שאלות נפוצות</h1>
        <p>מצאנו תשובות לשאלות הנפוצות ביותר</p>
      </div>

      <div className="faq-list">
        {faqs.map((faq, index) => (
          <div
            key={index}
            className={`faq-item ${openIndex === index ? 'open' : ''}`}
          >
            <button
              className="faq-question"
              onClick={() => toggleFAQ(index)}
              aria-expanded={openIndex === index}
            >
              <span>{faq.question}</span>
              <svg
                className="faq-icon"
                width="20"
                height="20"
                viewBox="0 0 20 20"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M5 7.5L10 12.5L15 7.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <div className="faq-answer">
              <p>{faq.answer}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default FAQ;
