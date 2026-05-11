from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException
from app.models.course import Course
from app.models.lesson import Lesson
from app.models.teacher import Teacher
from app.models.course_rating import CourseRating


class CourseService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_courses(self) -> List[Dict[str, Any]]:
        rating_subquery = (
            self.db.query(
                CourseRating.course_id,
                func.avg(CourseRating.rating).label("average_rating"),
                func.count(CourseRating.id).label("total_ratings"),
            )
            .filter(CourseRating.deleted_at.is_(None))
            .group_by(CourseRating.course_id)
            .subquery()
        )

        rows = (
            self.db.query(
                Course,
                func.coalesce(rating_subquery.c.average_rating, 0.0).label("average_rating"),
                func.coalesce(rating_subquery.c.total_ratings, 0).label("total_ratings"),
            )
            .outerjoin(rating_subquery, Course.id == rating_subquery.c.course_id)
            .filter(Course.deleted_at.is_(None))
            .all()
        )

        return [
            {
                "id": course.id,
                "name": course.name,
                "description": course.description,
                "thumbnail": course.thumbnail,
                "slug": course.slug,
                "average_rating": float(average_rating),
                "total_ratings": total_ratings,
            }
            for course, average_rating, total_ratings in rows
        ]

    def get_course_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        course = (
            self.db.query(Course)
            .options(joinedload(Course.teachers), joinedload(Course.lessons))
            .filter(Course.slug == slug)
            .filter(Course.deleted_at.is_(None))
            .first()
        )

        if not course:
            return None

        stats = self._compute_rating_stats(course.id)

        return {
            "id": course.id,
            "name": course.name,
            "description": course.description,
            "thumbnail": course.thumbnail,
            "slug": course.slug,
            "teacher_id": [teacher.id for teacher in course.teachers],
            "classes": [
                {
                    "id": lesson.id,
                    "name": lesson.name,
                    "description": lesson.description,
                    "slug": lesson.slug,
                }
                for lesson in course.lessons
                if lesson.deleted_at is None
            ],
            **stats,
        }

    def _compute_rating_stats(self, course_id: int) -> Dict[str, Any]:
        result = (
            self.db.query(
                func.avg(CourseRating.rating).label("average_rating"),
                func.count(CourseRating.id).label("total_ratings"),
            )
            .filter(CourseRating.course_id == course_id)
            .filter(CourseRating.deleted_at.is_(None))
            .one()
        )
        return {
            "average_rating": float(result.average_rating) if result.average_rating is not None else 0.0,
            "total_ratings": result.total_ratings if result.total_ratings is not None else 0,
        }

    def upsert_rating(self, slug: str, user_id: str, rating: int) -> Dict[str, Any]:
        course = (
            self.db.query(Course)
            .filter(Course.slug == slug)
            .filter(Course.deleted_at.is_(None))
            .first()
        )
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        now = datetime.utcnow()
        stmt = pg_insert(CourseRating).values(
            course_id=course.id,
            user_id=user_id,
            rating=rating,
            created_at=now,
            updated_at=now,
        ).on_conflict_do_update(
            constraint="uq_course_ratings_course_user",
            set_={"rating": rating, "updated_at": now, "deleted_at": None},
        )
        self.db.execute(stmt)
        self.db.commit()

        stats = self._compute_rating_stats(course.id)
        return {
            "course_id": course.id,
            "user_id": user_id,
            "rating": rating,
            **stats,
        }

    def get_user_rating(self, slug: str, user_id: str) -> Optional[CourseRating]:
        course = (
            self.db.query(Course)
            .filter(Course.slug == slug)
            .filter(Course.deleted_at.is_(None))
            .first()
        )
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        return (
            self.db.query(CourseRating)
            .filter(CourseRating.course_id == course.id)
            .filter(CourseRating.user_id == user_id)
            .filter(CourseRating.deleted_at.is_(None))
            .first()
        )
