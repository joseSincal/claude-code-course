from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.base import engine, get_db
from app.services.course_service import CourseService
from app.schemas.rating import RatingCreate, RatingResponse, UserRatingResponse

app = FastAPI(title=settings.project_name, version=settings.version)


def get_course_service(db: Session = Depends(get_db)) -> CourseService:
    return CourseService(db)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Bienvenido a Platziflix API"}


@app.get("/health")
def health() -> dict[str, str | bool | int]:
    health_status = {
        "status": "ok",
        "service": settings.project_name,
        "version": settings.version,
        "database": False,
    }

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM courses"))
            row = result.fetchone()
            if row:
                health_status["database"] = True
                health_status["courses_count"] = row[0]
            else:
                health_status["database"] = True
                health_status["courses_count"] = 0
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["database_error"] = str(e)

    return health_status


@app.get("/courses")
def get_courses(course_service: CourseService = Depends(get_course_service)) -> list:
    return course_service.get_all_courses()


@app.get("/courses/{slug}")
def get_course_by_slug(slug: str, course_service: CourseService = Depends(get_course_service)) -> dict:
    course = course_service.get_course_by_slug(slug)

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return course


@app.post("/courses/{slug}/ratings", response_model=RatingResponse)
def upsert_rating(
    slug: str,
    body: RatingCreate,
    course_service: CourseService = Depends(get_course_service),
) -> RatingResponse:
    return course_service.upsert_rating(slug, body.user_id, body.rating)


@app.get("/courses/{slug}/ratings/me", response_model=UserRatingResponse)
def get_user_rating(
    slug: str,
    user_id: str,
    course_service: CourseService = Depends(get_course_service),
) -> UserRatingResponse:
    rating = course_service.get_user_rating(slug, user_id)

    if rating is None:
        raise HTTPException(status_code=404, detail="Rating not found")

    return UserRatingResponse(
        course_id=rating.course_id,
        user_id=rating.user_id,
        rating=rating.rating,
    )
