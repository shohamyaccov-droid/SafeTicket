import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SellCompletionModal from './SellCompletionModal';

describe('SellCompletionModal copy', () => {
  it('explains that bank/Bit details come after the ticket upload', () => {
    render(
      <SellCompletionModal
        saving={false}
        error=""
        fieldErrors={{}}
        onBack={() => {}}
        onSubmit={() => {}}
      />,
    );
    expect(
      screen.getByText('רק שם, אימייל וסיסמה. הוספת חשבון בנק או ביט תתבצע לאחר העלאת הכרטיס.'),
    ).toBeInTheDocument();
  });
});
