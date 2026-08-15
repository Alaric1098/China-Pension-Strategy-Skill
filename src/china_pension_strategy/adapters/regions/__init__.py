"""Region adapter factory.

Routes a person-input `region` value to the matching region adapter.

Only implemented regions are available. Valid-but-unimplemented regions
(and unknown region values) fail with a stable error code so the CLI can
report them safely without leaking internals.
"""

from __future__ import annotations

from typing import Protocol

from china_pension_strategy.adapters.regions.beijing import (
    BeijingRegionAdapter,
    RegionMappingError,
)
from china_pension_strategy.adapters.regions.chengdu import ChengduRegionAdapter
from china_pension_strategy.adapters.regions.chongqing import ChongqingRegionAdapter
from china_pension_strategy.adapters.regions.guangzhou import GuangzhouRegionAdapter
from china_pension_strategy.adapters.regions.hangzhou import HangzhouRegionAdapter
from china_pension_strategy.adapters.regions.nanjing import NanjingRegionAdapter
from china_pension_strategy.adapters.regions.shanghai import ShanghaiRegionAdapter
from china_pension_strategy.adapters.regions.shenzhen import ShenzhenRegionAdapter
from china_pension_strategy.adapters.regions.tianjin import TianjinRegionAdapter
from china_pension_strategy.adapters.regions.wuhan import WuhanRegionAdapter


class RegionAdapter(Protocol):
    """Minimal structural contract every region adapter implements."""

    def to_analysis_request(self, person_input: dict) -> object: ...


_REGISTRY: dict[str, type[RegionAdapter]] = {
    "beijing": BeijingRegionAdapter,
    "shanghai": ShanghaiRegionAdapter,
    "guangzhou": GuangzhouRegionAdapter,
    "shenzhen": ShenzhenRegionAdapter,
    "hangzhou": HangzhouRegionAdapter,
    "chengdu": ChengduRegionAdapter,
    "wuhan": WuhanRegionAdapter,
    "nanjing": NanjingRegionAdapter,
    "tianjin": TianjinRegionAdapter,
    "chongqing": ChongqingRegionAdapter,
}


def create_region_adapter(
    region: str,
    *,
    engine_version: str = "0.1.0",
) -> RegionAdapter:
    """Return the region adapter for `region`.

    Raises `RegionMappingError` with `REGION_UNKNOWN` for values outside
    the schema enum.
    """
    if region not in _REGISTRY:
        raise RegionMappingError(
            "REGION_UNKNOWN",
            f"unknown region: {region}",
        )
    return _REGISTRY[region](engine_version=engine_version)


__all__ = ["create_region_adapter", "RegionAdapter", "RegionMappingError"]
