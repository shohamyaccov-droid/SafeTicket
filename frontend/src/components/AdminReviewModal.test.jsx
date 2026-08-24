import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AdminReviewModal from './AdminReviewModal';

const groupedTickets = [
  {
    id: 10,
    listing_group_id: 'g1',
    event_name: 'הופעה',
    ticket_file_url: 'https://example.test/t1.pdf',
    ticket_file_kind: 'pdf',
    event: { venue_detail: { sections: [{ name: 'Block 12' }, { name: 'דשא' }] } },
  },
  {
    id: 11,
    listing_group_id: 'g1',
    ticket_file_url: 'https://example.test/photo.jpg',
    ticket_file_kind: 'image',
    event: { venue_detail: { sections: [{ name: 'Block 12' }, { name: 'דשא' }] } },
  },
];

describe('AdminReviewModal', () => {
  it('renders a PDF iframe and a section dropdown, then auto-increments seats in the group', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const onApprove = vi.fn();
    render(
      <AdminReviewModal
        ticket={groupedTickets[0]}
        tickets={groupedTickets}
        onClose={() => {}}
        onSave={onSave}
        onApprove={onApprove}
      />,
    );

    expect(screen.getByTitle('תצוגת כרטיס #10')).toBeInTheDocument();
    expect(screen.getByTitle('תצוגת כרטיס #10').tagName).toBe('IFRAME');
    expect(screen.getByLabelText('גוש').tagName).toBe('SELECT');

    await user.selectOptions(screen.getByLabelText('גוש'), 'דשא');
    await user.type(screen.getByLabelText('שורה'), '7');
    await user.type(screen.getByLabelText('כיסא'), '12');

    const preview = screen.getByTestId('admin-review-bulk-preview');
    expect(preview).toHaveTextContent('כיסא 12');
    expect(preview).toHaveTextContent('כיסא 13');

    await user.click(screen.getByRole('button', { name: 'שמור' }));
    expect(onSave).toHaveBeenCalledWith(
      groupedTickets[0],
      { section: 'דשא', row: '7', seat: '12' },
      { applyToGroup: true },
    );

    await user.click(screen.getByRole('button', { name: 'אישור ופרסום לכל הקבוצה' }));
    expect(onApprove).toHaveBeenCalledWith(
      groupedTickets[0],
      { section: 'דשא', row: '7', seat: '12' },
      { applyToGroup: true, approveGroup: true },
    );
  });

  it('shows an image tag for photo tickets', async () => {
    const user = userEvent.setup();
    render(
      <AdminReviewModal
        ticket={groupedTickets[0]}
        tickets={groupedTickets}
        onClose={() => {}}
        onSave={() => {}}
        onApprove={() => {}}
      />,
    );
    await user.click(screen.getByRole('tab', { name: 'כרטיס 2' }));
    const image = screen.getByAltText('כרטיס #11');
    expect(image.tagName).toBe('IMG');
    expect(image).toHaveAttribute('src', 'https://example.test/photo.jpg');
  });
});
