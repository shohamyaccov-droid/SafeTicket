"""Mirror of frontend pickMostSupplyEventId — keeps badge tie-break spec testable in Django."""


def pick_most_supply_event_id(events):
    if not events:
        return None
    max_count = max(int(ev.get('tickets_count') or 0) for ev in events)
    if max_count <= 0:
        return None
    tied = [ev for ev in events if int(ev.get('tickets_count') or 0) == max_count]
    if len(tied) == 1:
        return tied[0].get('id')
    earliest = sorted(tied, key=lambda ev: ev.get('date') or '')[0]
    return earliest.get('id')
