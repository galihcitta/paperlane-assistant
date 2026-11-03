from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SizeCode = Literal["A3", "A4", "A5", "LETTER", "LEGAL", "OTHER"]
StockStatus = Literal["in_stock", "out_of_stock", "discontinued", "unknown"]

REQUIRED = ["sku", "product_name", "size_code", "weight_gsm", "sheets_per_pack", "list_price_satang", "stock_status"]


class Tier(BaseModel):
    min_qty: int
    unit_price_satang: int


class Item(BaseModel):
    """One sellable SKU. Money is integer satang (1 THB = 100 satang), excluding VAT."""
    sku: str
    product_url: str
    product_name: str
    category: str | None = None
    product_type: Literal["paper", "printed_flyer"]
    brand: str | None = None
    size_code: SizeCode | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    weight_gsm: int | None = None
    weight_lb_stated: int | None = None
    weight_source: Literal["stated", "converted_from_lb"] | None = None
    colour: str | None = None
    colour_raw: str | None = None
    finish: str | None = None
    finish_raw: str | None = None
    sides: Literal[1, 2] | None = None
    colour_mode: Literal["cmyk", "bw"] | None = None
    pack_unit: Literal["ream", "pack"] = "pack"
    sheets_per_pack: int | None = None
    list_price_satang: int | None = None
    sale_price_satang: int | None = None
    stock_status: StockStatus = "unknown"
    stock_raw: str | None = None
    back_in_stock: date | None = None
    extraction: Literal["deterministic", "llm"] = "deterministic"
    source_url: str
    crawled_at: str
    tiers: list[Tier] = Field(default_factory=list)
    tiers_url: str | None = None
    quotable: bool = True                  # False = data problem found at ingest; never priced
    quarantine_reason: str | None = None

    def quarantine(self, reason: str):
        self.quotable = False
        self.quarantine_reason = "; ".join(x for x in (self.quarantine_reason, reason) if x)

    def missing_required(self) -> list[str]:
        return [f for f in REQUIRED if getattr(self, f) in (None, "", "unknown")]

    def validation_errors(self) -> list[str]:
        errs = [f"missing {f}" for f in self.missing_required()]
        if self.list_price_satang is not None and self.list_price_satang <= 0:
            errs.append("list price <= 0")
        if self.sale_price_satang is not None and self.list_price_satang and self.sale_price_satang >= self.list_price_satang:
            errs.append("sale price not below list price")
        prev = self.list_price_satang
        for t in sorted(self.tiers, key=lambda t: t.min_qty):
            if t.min_qty < 1:
                errs.append(f"tier min_qty {t.min_qty} < 1")
            if prev is not None and t.unit_price_satang >= prev:
                errs.append(f"tier {t.min_qty} price not below previous price")
            prev = t.unit_price_satang
        return errs
