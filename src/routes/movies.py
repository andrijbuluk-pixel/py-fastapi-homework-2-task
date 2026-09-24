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


async def get_or_create(db: AsyncSession, model, **kwargs):
    instance = await db.scalar(select(model).filter_by(**kwargs))

    if not instance:
        instance = model(**kwargs)
        db.add(instance)
    return instance


async def get_relations_data(movie_date, db: AsyncSession = Depends(get_db)):
    country_db = await get_or_create(db, CountryModel, name=movie_date.country)

    genres_db = [
        await get_or_create(db, GenreModel, name=name)
        for name in movie_date.genres
    ]

    actors_db = [
        await get_or_create(db, ActorModel, name=name)
        for name in movie_date.actors
    ]

    languages_db = [
        await get_or_create(db, LanguageModel, name=name)
        for name in movie_date.languages
    ]

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

    pgm = select(MovieModel).limit(per_page).offset((page - 1) * per_page).order_by(MovieModel.id.desc())
    result = await db.execute(pgm)
    movies = result.scalars().all()

    if total_items == 0 or page > total_pages or not movies:
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


@router.delete("/movies/{movie_id}/", status_code=204)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
):
    movie = await get_movie_relations(movie_id, db)

    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()
    return


@router.patch("/movies/{movie_id}/")
async def update_movie(
        movie_id: int,
        movie: MovieUpdateSchema,
        db: AsyncSession = Depends(get_db),
):
    movie_search = await db.scalar(
        select(MovieModel).where(
            MovieModel.id == movie_id,
        )
    )

    if movie_search is None:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    update_data = movie.model_dump(exclude_unset=True)

    if "country" in update_data:
        country_name = update_data.pop("country")
        movie_search.country = await get_or_create(
            db, CountryModel, name=country_name, code=country_name[:3].upper()
        )

    if "genres" in update_data:
        genres_name = update_data.pop("genres")
        movie_search.genres = [
            await get_or_create(db, GenreModel, name=name)
            for name in genres_name
        ]

    if "actors" in update_data:
        actors_name = update_data.pop("actors")
        movie_search.actors = [
            await get_or_create(db, ActorModel, name=name)
            for name in actors_name
        ]

    if "languages" in update_data:
        languages_name = update_data.pop("languages")
        movie_search.languages = [
            await get_or_create(db, LanguageModel, name=name)
            for name in languages_name
        ]

    for key, value in update_data.items():
        setattr(movie_search, key, value)

    await db.commit()
    return {"detail": "Movie updated successfully."}
