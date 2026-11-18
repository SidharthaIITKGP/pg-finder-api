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


def test_no_budget_returns_all_matching_prices():
    out = client.post('/search_pgs', json={'city':'Bangalore','area':'Koramangala',
                                         'pg_type':'boys','room_type':'sharing'}).json()
    assert out['status'] == 'matches_found'
    assert [m['monthly_price_inr'] for m in out['matches']] == [8500, 11000]
    assert out['filters']['max_budget_inr'] is None
    assert out['filters']['min_budget_inr'] is None


def test_upper_limit_includes_cheaper_properties():
    out = client.post('/search_pgs', json={'city':'Bengaluru','area':'Koramangala',
                                         'pg_type':'boys','room_type':'single',
                                         'max_budget': 40000}).json()
    assert out['status'] == 'matches_found'
    assert [m['monthly_price_inr'] for m in out['matches']] == [15500, 17000]


def test_range_inclusive():
    out = client.post('/search_pgs', json={'city':'Bengaluru','area':'Koramangala',
                                         'pg_type':'boys','room_type':'sharing',
                                         'min_budget': 11000, 'max_budget': 12000}).json()
    assert out['status'] == 'matches_found'
    assert [m['monthly_price_inr'] for m in out['matches']] == [11000]


def test_lower_bound_without_upper_bound():
    out = client.post('/search_pgs', json={'city':'Bengaluru','area':'Koramangala',
                                         'pg_type':'boys','room_type':'sharing',
                                         'min_budget': 9000}).json()
    assert out['status'] == 'matches_found'
    assert [m['monthly_price_inr'] for m in out['matches']] == [11000]


def test_no_results_for_30k_40k_range():
    out = client.post('/search_pgs', json={'city':'Bengaluru','area':'Koramangala',
                                         'pg_type':'boys','room_type':'sharing',
                                         'min_budget': 30000, 'max_budget': 40000}).json()
    assert out['status'] == 'no_matches'
    assert out['matches'] == []


def test_invalid_budget_range():
    out = client.post('/search_pgs', json={'city':'Bengaluru','area':'Koramangala',
                                         'pg_type':'boys','room_type':'sharing',
                                         'min_budget': 40000, 'max_budget': 30000}).json()
    assert out['status'] == 'invalid_budget_range'
    assert out['matches'] == []


def test_invalid_budget_does_not_silently_broaden():
    out = client.post('/search_pgs', json={'city':'Bengaluru','area':'Koramangala',
                                         'pg_type':'boys','room_type':'sharing',
                                         'max_budget': 'oops'}).json()
    assert out['status'] == 'invalid_budget'
    assert 'max_budget' in out['invalid_fields']
