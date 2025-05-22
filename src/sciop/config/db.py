from pydantic import BaseModel


class DBConfig(BaseModel):
    """
    Configuration of the database

    (except its path, which is in PathConfig)
    """

    echo: bool = False
    """Echo all queries made to the database"""
    pool_size: int = 10
    """Number of active database connections to maintain"""
    overflow_size: int = 20
    """Additional database connections that are not allowed to sleep"""
