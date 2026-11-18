from fastapi.testclient import TestClient
from app import PROPERTIES, app

client = TestClient(app)


def test_inventory_size_and_health():
    assert len(PROPERTIES) == 15
    assert client.get('/health').json()['properties'] == 15


def test_koramangala_boys_under_12k():
    r = client.post('/search_pgs', json={'city': 'Bangalore', 'area': 'Koramangala',
                                       'pg_type': 'boys', 'max_budget': '12k', 'room_type': 'sharing'})
    assert r.status_code == 200
    out = r.json()
    assert out['status'] == 'matches_found'
    assert [p['monthly_price_inr'] for p in out['matches']] == [8500, 11000]
    assert all(p['pg_type'] == 'boys' for p in out['matches'])


def test_no_silent_area_expansion():
    out = client.post('/search_pgs', json={'city': 'Bengaluru', 'area': 'Indiranagar',
                                         'pg_type': 'boys', 'max_budget': 20000,
                                         'room_type': 'sharing'}).json()
    assert out['status'] == 'no_matches'
    assert out['matches'] == []


def test_no_unverified_room_type():
    out = client.post('/search_pgs', json={'city': 'Hyderabad', 'area': 'Kondapur',
                                         'pg_type': 'boys', 'max_budget': 9000,
                                         'room_type': 'single'}).json()
    assert out['status'] == 'no_matches'


def test_missing_fields_asks_without_guessing():
    out = client.post('/search_pgs', json={'city': 'Pune', 'area': None,
                                         'pg_type': 'girls', 'max_budget': 15000,
                                         'room_type': 'sharing'}).json()
    assert out['status'] == 'need_more_info'
    assert 'area' in out['missing_fields']


def test_returned_matches_max_three_and_under_budget():
    out = client.post('/search_pgs', json={'city': 'Pune', 'area': 'Hinjewadi',
                                         'pg_type': 'co-living', 'max_budget': 10000,
                                         'room_type': 'sharing'}).json()
    assert out['status'] == 'matches_found'
    assert len(out['matches']) <= 3
    assert all(m['monthly_price_inr'] <= 10000 for m in out['matches'])
