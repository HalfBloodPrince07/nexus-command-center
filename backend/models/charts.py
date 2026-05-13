from pydantic import BaseModel, model_validator
from typing import Literal, Any

class ChartSeries(BaseModel):
    name: str
    data: list[dict[str, Any]]
    color: str | None = None

class GraphNode(BaseModel):
    id: str
    label: str
    size: float = 1.0
    color: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = {}

class GraphEdge(BaseModel):
    source: str
    target: str
    label: str | None = None
    weight: float = 1.0
    color: str | None = None

class ChartPayload(BaseModel):
    id: str
    type: Literal["line", "bar", "radar", "heatmap", "graph", "calendar"]
    title: str
    series: list[ChartSeries] | None = None
    nodes: list[GraphNode] | None = None
    edges: list[GraphEdge] | None = None
    x_label: str | None = None
    y_label: str | None = None
    meta: dict[str, Any] = {}

    @model_validator(mode="after")
    def validate_chart_data(self):
        if self.type == "graph":
            if not self.nodes or not self.edges:
                raise ValueError("Graph charts require non-empty nodes and edges")
        elif self.type in ("line", "bar", "radar"):
            if not self.series:
                raise ValueError(f"{self.type} charts require non-empty series")
        return self
