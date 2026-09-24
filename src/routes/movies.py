import math

from fastapi import APIRouter, Depends, HTTPException, Query
from numpy.ma.core import mvoid
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from database import get_db, MovieModel
from database.models import CountryModel, GenreModel, ActorModel, LanguageModel
from schemas.movies import (
    MovieListResponseSchema,
    MovieDetailSchema,
    MovieCreateSchema,
    MovieUpdateSchema
)

router = APIRouter()


async def get_movie_relations(movie_id: int, db: AsyncSession = Depends(get_db)):
    loader = (
        select(MovieModel).options(
            joinedload(MovieModel.country),
            selectinload(MovieModel.genres),
            selectinload(MovieModel.actors),
            selectinload(MovieModel.languages),
        ).where(MovieModel.id == movie_id)
    )
    return await db.scalar(loader)


async def get_relations_data(movie_date, db: AsyncSession = Depends(get_db)):
    country_db = await db.scalar(
        select(CountryModel).where(CountryModel.code == movie_date.country)
    )

    genres_db = (
        await db.scalars(
            select(GenreModel).where(GenreModel.name.in_(movie_date.genres))
        )
    ).all()

    actors_db = (
        await db.scalars(
            select(ActorModel).where(ActorModel.name.in_(movie_date.actors))
        )
    ).all()

    languages_db = (
        await db.scalars(
            select(LanguageModel).where(LanguageModel.name.in_(movie_date.languages))
        )
    ).all()

    return country_db, genres_db, actors_db, languages_db


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_movies_list(
        db: AsyncSession = Depends(get_db),
        page: int = Query(default=1, ge=1),
        per_page: int = Query(default=10, ge=1, le=20),
):
    count_items = select(func.count()).select_from(MovieModel)
    total_items = await db.scalar(count_items)

    total_pages = math.ceil(total_items / per_page)

    if page > 1:
        prev_page = f"/theater/movies/?page={page - 1}&per_page={per_page}"

    else:
        prev_page = None

    if page < total_pages:
        next_page = f"/theater/movies/?page={page + 1}&per_page={per_page}"
    else:
        next_page = None

    pgm = select(MovieModel).limit(per_page).offset((page - 1) * per_page)
    result = await db.execute(pgm)
    movies = result.scalars().all()

    if total_items == 0 or page > total_pages:
        raise HTTPException(status_code=404, detail="No movies found.")

    return {
        "movies": movies,
        "prev_page": prev_page,
        "next_page": next_page,
        "total_pages": total_pages,
        "total_items": total_items,
    }


@router.post("/movies/", response_model=MovieDetailSchema, status_code=201)
async def create_movie(
        movie: MovieCreateSchema,
        db: AsyncSession = Depends(get_db),
):
    country_db, genres_db, actors_db, languages_db = await get_relations_data(movie, db)

    exist_movie = await db.scalar(
        select(MovieModel).where(
            MovieModel.name == movie.name,
            MovieModel.date == movie.date
        )
    )

    if exist_movie is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A movie with the name '{movie.name}' and release date '{movie.date}' already exists."
        )

    new_movie = MovieModel(
        name=movie.name,
        date=movie.date,
        score=movie.score,
        overview=movie.overview,
        status=movie.status,
        budget=movie.budget,
        revenue=movie.revenue,
        country=country_db,
        genres=list(genres_db),
        actors=list(actors_db),
        languages=list(languages_db),
    )

    db.add(new_movie)
    await db.commit()

    return await get_movie_relations(new_movie.id, db)


@router.get("/movies/{movie_id}/", response_model=MovieDetailSchema)
async def get_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
    movie = await get_movie_relations(movie_id, db)

    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")

    return movie

