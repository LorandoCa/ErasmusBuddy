from typing import Type
import sys
import os

# When CrewAI loads this file via spec_from_file_location it runs it as the
# pseudo-module "custom_tools.housing_search_tool" — relative imports fail
# because "custom_tools" is not a real package. We therefore add this file's
# parent directory (…/tools/) to sys.path so absolute imports work.
_tools_dir = os.path.dirname(os.path.abspath(__file__))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from pydantic import BaseModel, Field
from crewai.tools import BaseTool

import db_helper as _db_helper
search_housing_near = _db_helper.search_housing_near


class HousingSearchInput(BaseModel):
    """Input schema for HousingSearchTool."""
    anchor_query: str = Field(
        default="universidade",
        description="Name of the university, campus, faculty, or landmark (e.g. 'dei', 'fctuc', 'feup', 'tecnico', 'polo 1', 'universidade')."
    )
    city: str = Field(
        default="",
        description="Target city name: 'Coimbra', 'Porto', or 'Lisboa'."
    )
    radius_meters: float = Field(
        default=4000.0,
        description="Search radius in meters around the anchor (default 4000m)."
    )
    limit: int = Field(
        default=6,
        description="Maximum number of housing options to return (default 6)."
    )


class HousingSearchTool(BaseTool):
    name: str = "search_housing_near"
    description: str = (
        "Search real student housing (rooms in shared flats, university residences, dorms) "
        "near a campus or faculty in Coimbra, Porto, or Lisboa. Returns exact monthly rent in euros, "
        "whether expenses/utilities are included, address, neighborhood, distance in meters, and source."
    )
    args_schema: Type[BaseModel] = HousingSearchInput

    def _run(
        self,
        anchor_query: str = "universidade",
        city: str = "",
        radius_meters: float = 4000.0,
        limit: int = 6
    ) -> str:
        return search_housing_near(
            anchor_query=anchor_query,
            city=city,
            radius_meters=radius_meters,
            limit=limit,
        )
