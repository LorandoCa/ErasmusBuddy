from pydantic import BaseModel, Field

#FILE RESPONSIBLE FOR THE MODELS(OUTPUT FORMATS) USED
class CostEstimate(BaseModel):
    average_monthly: float = Field(description="Average monthly spending in euros, as a plain number (e.g. 180.0)")
    low: float = Field(description="Low end of the monthly range in euros, as a plain number")
    high: float = Field(description="High end of the monthly range in euros, as a plain number")
    sources: list[str] = Field(description="URLs of the pages where the figures were found")