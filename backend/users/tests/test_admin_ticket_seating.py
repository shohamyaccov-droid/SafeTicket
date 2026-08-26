from django.test import SimpleTestCase

from users.admin_ticket_seating import (
    extract_ticket_pdf_text,
    increment_seat_label,
    optional_seating_from_request,
    ticket_file_kind,
)


class IncrementSeatLabelTests(SimpleTestCase):
    def test_numeric_sequence(self):
        self.assertEqual(increment_seat_label('12', 0), '12')
        self.assertEqual(increment_seat_label('12', 1), '13')
        self.assertEqual(increment_seat_label('12', 2), '14')

    def test_preserves_padding_and_suffix(self):
        self.assertEqual(increment_seat_label('012', 1), '013')
        self.assertEqual(increment_seat_label('A12', 1), 'A13')
        self.assertEqual(increment_seat_label('12A', 1), '13A')

    def test_non_numeric_stays_put(self):
        self.assertEqual(increment_seat_label('דשא', 1), 'דשא')
        self.assertEqual(increment_seat_label('', 3), '')


class TicketFileKindTests(SimpleTestCase):
    def test_image_extension(self):
        ticket = type('T', (), {'pdf_file': type('F', (), {'name': 'tickets/pdfs/a.PNG'})()})()
        self.assertEqual(ticket_file_kind(ticket), 'image')

    def test_pdf_default(self):
        ticket = type('T', (), {'pdf_file': type('F', (), {'name': 'tickets/pdfs/a.pdf'})()})()
        self.assertEqual(ticket_file_kind(ticket), 'pdf')


class ExtractTicketPdfTextTests(SimpleTestCase):
    def test_images_are_skipped(self):
        ticket = type('T', (), {'pdf_file': type('F', (), {'name': 'tickets/pdfs/a.jpg'})()})()
        self.assertEqual(extract_ticket_pdf_text(ticket), '')

    def test_missing_file_is_empty(self):
        ticket = type('T', (), {'pdf_file': None})()
        self.assertEqual(extract_ticket_pdf_text(ticket), '')


class OptionalSeatingFromRequestTests(SimpleTestCase):
    def test_parses_per_ticket_seat_overrides(self):
        request = type(
            'R',
            (),
            {
                'data': {
                    'section': 'Block 12',
                    'row': '7',
                    'seat': '16',
                    'seats': [
                        {'ticket_id': 10, 'seat': '16'},
                        {'ticket_id': 11, 'seat': '25'},
                    ],
                }
            },
        )()
        payload = optional_seating_from_request(request)
        self.assertEqual(payload['section'], 'Block 12')
        self.assertEqual(payload['seat'], '16')
        self.assertEqual(payload['seats_by_id'], {10: '16', 11: '25'})
