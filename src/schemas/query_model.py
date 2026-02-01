from pydantic import BaseModel


class QueryModel(BaseModel):
    """
    Data modelling class that extends base model class,
    this class will handle the data we will receive from
    api
    """

    company_name: str
