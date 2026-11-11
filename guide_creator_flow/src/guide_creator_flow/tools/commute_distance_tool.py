from typing import Type
import sys
import os

# When CrewAI loads this file via spec_from_file_location it runs it as the
# pseudo-module "custom_tools.commute_distance_tool" — relative imports fail
# because "custom_tools" is not a real package. We therefore add this file's
# parent directory (…/tools/) to sys.path so absolute imports work.
_tools_dir = os.path.dirname(os.path.abspath(__file__))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from pydantic import BaseModel, Field
from crewai.tools import BaseTool

import db_helper as _db_helper
distance_between_places = _db_helper.distance_between_places


class CommuteDistanceInput(BaseModel):
    """Input schema for CommuteDistanceTool."""
    origin_query: str = Field(
        description="Starting location, neighborhood, or accommodation address (e.g. 'Celas', 'Baixa', 'Olivais', or an address)."
    )
    target_query: str = Field(
        description="Destination university, campus, or faculty (e.g. 'dei', 'polo 1', 'feup', 'tecnico')."
    )
    city: str = Field(
        default="",
        description="City name (e.g., 'Coimbra', 'Porto', 'Lisboa')."
    )


class CommuteDistanceTool(BaseTool):
    name: str = "distance_between_places"
    description: str = (
        "Calculates the distance in meters and kilometers between two places in Coimbra, Porto, or Lisboa "
        "(e.g. from student housing/neighborhood to university campus). Use this to estimate commute distance and travel practicality."
    )
    args_schema: Type[BaseModel] = CommuteDistanceInput

    def _run(self, origin_query: str, target_query: str, city: str = "") -> str:
        return distance_between_places(
            origin_query=origin_query,
            target_query=target_query,
            origin_city=city,
            target_city=city,
        )
