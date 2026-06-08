"""GraphQL router via Strawberry."""
import strawberry
from fastapi import APIRouter
from strawberry.fastapi import GraphQLRouter

@strawberry.type
class Query:
    @strawberry.field
    def ping(self) -> str:
        return "pong"

schema = strawberry.Schema(query=Query)
graphql_router: APIRouter = GraphQLRouter(schema)
