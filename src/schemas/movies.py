import datetime

from pydantic import BaseModel, Field, field_validator

from database.models import (
    MovieStatusEnum,
)


class GenreSchema(BaseModel):
    id: int
    name: str


class ActorSchema(BaseModel):
    id: int
    name: str


class CountrySchema(BaseModel):
    id: int
    code: str
    name: str | None = None


class LanguageSchema(BaseModel):
    id: int
    name: str


class MovieListItemSchema(BaseModel):
    id: int = Field(
        json_schema_extra={
            "readOnly": True,
        }
    )
    name: str
    date: datetime.date
    score: float
    overview: str

    class Config:
        from_attributes = True


class MovieListResponseSchema(BaseModel):
    movies: list[MovieListItemSchema]
    prev_page: str | None
    next_page: str | None
    total_pages: int
    total_items: int

    class Config:
        from_attributes = True


class MovieDetailSchema(BaseModel):
    id: int = Field(
        json_schema_extra={
            "readOnly": True,
        }
    )
    name: str
    date: datetime.date
    score: float
    overview: str
    status: MovieStatusEnum
    budget: float
    revenue: float
    country: CountrySchema
    genres: list[GenreSchema]
    actors: list[ActorSchema]
    languages: list[LanguageSchema]

    class Config:
        from_attributes = True


class MovieCreateSchema(BaseModel):
    name: str = Field(max_length=255)
    date: datetime.date
    score: float = Field(ge=0, le=100)
    overview: str
    status: MovieStatusEnum
    budget: float = Field(ge=0)
    revenue: float = Field(ge=0)
    country: str
    genres: list[str]
    actors: list[str]
    languages: list[str]

    class Config:
        from_attributes = True

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: datetime.date):
        max_date = datetime.date.today().replace(
            year=datetime.date.today().year + 1
        )
        if v > max_date:
            raise ValueError("Invalid date")
        return v


class MovieUpdateSchema(BaseModel):
    name: str | None = None
    date: datetime.date | None = None
    score: float | None = None
    overview: str | None = None
    status: MovieStatusEnum | None = None
    budget: float | None = None
    revenue: float | None = None
