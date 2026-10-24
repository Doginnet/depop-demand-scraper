from datetime import datetime
from pydantic import BaseModel, Field


class ProductItem(BaseModel):
    id: int
    slug: str
    title: str
    description: str = ""
    price: float
    currency: str = "USD"
    url: str
    image_url: str | None = None
    brand_name: str | None = None
    like_count: int = 0
    offers_count: int = 0
    in_bags_count: int = 0
    demand_score: float = 0.0
    scraped_at: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_api_object(cls, obj: dict, base_url: str = "https://www.depop.com") -> "ProductItem":
        slug = obj.get("slug", "")
        url = f"{base_url}/products/{slug}/" if slug else ""

        # Extract title from description or slug
        desc = (obj.get("description") or "").strip()
        first_line = desc.split("\n")[0].strip() if desc else ""
        if first_line and len(first_line) <= 120:
            title = first_line
        else:
            # Fallback title from slug
            title = slug.replace("-", " ").title()

        # Extract price
        price_val = 0.0
        pricing = obj.get("pricing") or {}
        current_price = pricing.get("current_price") or {}
        total_price_str = current_price.get("total_price")
        if total_price_str:
            try:
                price_val = float(total_price_str)
            except (ValueError, TypeError):
                price_val = 0.0
        else:
            price_breakdown = current_price.get("price_breakdown") or {}
            amount_str = (price_breakdown.get("price") or {}).get("amount")
            if amount_str:
                try:
                    price_val = float(amount_str)
                except (ValueError, TypeError):
                    price_val = 0.0

        currency = pricing.get("currency") or "USD"

        # Image preview URL
        image_url = None
        preview = obj.get("preview") or {}
        formats = preview.get("formats") or {}
        for fmt_key in ["P0", "P8", "P7", "P1"]:
            if fmt_key in formats and formats[fmt_key].get("url"):
                image_url = formats[fmt_key]["url"]
                break

        if not image_url:
            pictures = obj.get("pictures") or []
            if pictures and isinstance(pictures[0], dict):
                pic_formats = pictures[0].get("formats") or {}
                for fmt_key in ["P0", "P8", "P7", "P1"]:
                    if fmt_key in pic_formats and pic_formats[fmt_key].get("url"):
                        image_url = pic_formats[fmt_key]["url"]
                        break

        return cls(
            id=obj.get("id", 0),
            slug=slug,
            title=title,
            description=desc,
            price=price_val,
            currency=currency,
            url=url,
            image_url=image_url,
            brand_name=obj.get("brand_name"),
            like_count=obj.get("like_count") or 0,
        )


class SearchResponseMeta(BaseModel):
    total_count: int = 0
    has_more: bool = False
    cursor: str = ""
