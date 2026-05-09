from dataclasses import dataclass


@dataclass
class CompanyData:
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float | None
    pe_ratio: float | None
    revenue_growth_yoy: float | None
    earnings_growth_yoy: float | None
    dividend_yield: float | None
    description: str
    recent_news: list[str]


async def fetch_company_data(ticker: str) -> CompanyData | None:
    return None
