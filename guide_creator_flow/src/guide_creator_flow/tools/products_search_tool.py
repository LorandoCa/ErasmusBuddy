from typing import Type
import sys
import os

# When CrewAI loads this file via spec_from_file_location it runs it as the
# pseudo-module "custom_tools.products_search_tool" — relative imports fail
# because "custom_tools" is not a real package. We therefore add this file's
# parent directory (…/tools/) to sys.path so absolute imports work.
_tools_dir = os.path.dirname(os.path.abspath(__file__))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from pydantic import BaseModel, Field
from crewai.tools import BaseTool

import db_helper as _db_helper
search_products = _db_helper.search_products


class ProductsSearchInput(BaseModel):
    """Input schema for ProductsSearchTool."""
    query: str = Field(
        description="Short product keyword (e.g. 'arroz', 'massa', 'leite', 'frango', 'ovos', 'azeite', 'atum', 'cafe')."
    )
    retailer: str = Field(
        default="",
        description="Optional retailer: 'Continente' or 'Pingo Doce' (leave empty for both)."
    )
    limit: int = Field(
        default=6,
        description="Maximum number of products to return."
    )


class ProductsSearchTool(BaseTool):
    name: str = "search_supermarket_products"
    description: str = (
        "Searches real grocery and staple food product prices in Portuguese supermarkets (Continente and Pingo Doce). "
        "Returns product name, brand, package size, price in euros, unit price, and source."
    )
    args_schema: Type[BaseModel] = ProductsSearchInput

    def _run(self, query: str = "", retailer: str = "", limit: int = 6) -> str:
        return search_products(query=query, retailer=retailer, limit=limit)
