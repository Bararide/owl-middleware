from pydantic import BaseModel


class SemanticEdge(BaseModel):
    edge_from: str
    edge_to: str
    weight: float
