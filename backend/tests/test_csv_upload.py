import io

from app.services.csv_parser import parse_csv, parse_trading212_csv, parse_generic_csv


def test_parse_generic_csv():
    csv_content = """ticker,name,quantity,average_cost_basis
AAPL,Apple Inc,10,150.50
TSLA,Tesla Inc,5,220.00
MSFT,Microsoft Corp,20,310.25"""

    holdings = parse_generic_csv(csv_content)
    assert len(holdings) == 3
    assert holdings[0].ticker == "AAPL"
    assert holdings[0].name == "Apple Inc"
    assert holdings[0].quantity == 10
    assert holdings[0].average_cost_basis == 150.50
    assert holdings[1].ticker == "TSLA"
    assert holdings[2].ticker == "MSFT"


def test_parse_generic_csv_with_aliases():
    csv_content = """symbol,company,shares,avg_cost,ccy
aapl,Apple Inc,10,150.50,USD
tsla,Tesla Inc,5,220.00,USD"""

    holdings = parse_generic_csv(csv_content)
    assert len(holdings) == 2
    assert holdings[0].ticker == "AAPL"
    assert holdings[0].currency == "USD"


def test_parse_trading212_csv():
    csv_content = """Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency (Price / share),Exchange rate,Total (GBP)
Market buy,2024-01-15 10:00,US0378331005,AAPL_US_EQ,Apple Inc,10,150.50,USD,0.79,1189.00
Market buy,2024-02-10 14:00,US0378331005,AAPL_US_EQ,Apple Inc,5,160.00,USD,0.79,632.00
Market sell,2024-03-01 09:00,US0378331005,AAPL_US_EQ,Apple Inc,3,170.00,USD,0.80,408.00
Market buy,2024-01-20 11:00,US88160R1014,TSLA_US_EQ,Tesla Inc,8,220.00,USD,0.79,1390.40"""

    holdings = parse_trading212_csv(csv_content)
    assert len(holdings) == 2

    aapl = next(h for h in holdings if h.ticker == "AAPL_US_EQ")
    assert aapl.quantity == 12  # 10 + 5 - 3
    assert aapl.name == "Apple Inc"
    # avg cost = total_cost / remaining_shares = (10*150.50 + 5*160.00) / 12 = 2305/12 = 192.08
    assert round(aapl.average_cost_basis, 2) == 192.08

    tsla = next(h for h in holdings if h.ticker == "TSLA_US_EQ")
    assert tsla.quantity == 8


def test_parse_trading212_fully_sold():
    csv_content = """Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency (Price / share),Exchange rate,Total (GBP)
Market buy,2024-01-15 10:00,US0378331005,AAPL_US_EQ,Apple Inc,10,150.50,USD,0.79,1189.00
Market sell,2024-03-01 09:00,US0378331005,AAPL_US_EQ,Apple Inc,10,170.00,USD,0.80,1360.00"""

    holdings = parse_trading212_csv(csv_content)
    assert len(holdings) == 0  # fully sold, excluded


def test_auto_detect_trading212():
    csv_content = """Action,Time,ISIN,Ticker,Name,No. of shares,Price / share,Currency (Price / share)
Market buy,2024-01-15,US0378331005,AAPL,Apple,10,150.50,USD"""

    holdings = parse_csv(csv_content)
    assert len(holdings) == 1
    assert holdings[0].ticker == "AAPL"


def test_auto_detect_generic():
    csv_content = """ticker,name,quantity,average_cost_basis
AAPL,Apple Inc,10,150.50"""

    holdings = parse_csv(csv_content)
    assert len(holdings) == 1
    assert holdings[0].ticker == "AAPL"


async def test_upload_csv_endpoint(client, auth_headers):
    csv_content = b"ticker,name,quantity,average_cost_basis\nAAPL,Apple Inc,10,150.50\nTSLA,Tesla Inc,5,220.00"

    response = await client.post(
        "/api/portfolio/upload-csv",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["quantity"] == 10
    assert data[1]["ticker"] == "TSLA"


async def test_upload_csv_upserts_existing(client, auth_headers):
    # First upload
    csv1 = b"ticker,name,quantity,average_cost_basis\nAAPL,Apple Inc,10,150.50"
    await client.post(
        "/api/portfolio/upload-csv",
        files={"file": ("portfolio.csv", csv1, "text/csv")},
        headers=auth_headers,
    )

    # Second upload with updated quantity
    csv2 = b"ticker,name,quantity,average_cost_basis\nAAPL,Apple Inc,15,155.00"
    response = await client.post(
        "/api/portfolio/upload-csv",
        files={"file": ("portfolio.csv", csv2, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    assert data[0]["quantity"] == 15
    assert data[0]["average_cost_basis"] == 155.00

    # Verify only one holding exists
    holdings = await client.get("/api/portfolio/holdings", headers=auth_headers)
    assert len(holdings.json()) == 1


async def test_upload_csv_marks_portfolio_connected_for_onboarding(client, auth_headers):
    csv_content = b"ticker,name,quantity,average_cost_basis\nAAPL,Apple Inc,10,150.50"

    response = await client.post(
        "/api/portfolio/upload-csv",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 201

    onboarding = await client.get("/api/onboarding/status", headers=auth_headers)
    assert onboarding.status_code == 200
    data = onboarding.json()
    assert data["steps"]["import_holdings"]["done"] is True
    assert data["steps"]["import_holdings"]["count"] == 1
    assert data["current_step"] == "write_first_thesis"


async def test_upload_csv_requires_auth(client):
    csv_content = b"ticker,name,quantity,average_cost_basis\nAAPL,Apple,10,150"
    response = await client.post(
        "/api/portfolio/upload-csv",
        files={"file": ("portfolio.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 403
