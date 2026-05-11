from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    String,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from .base import BaseModel


class CourseRating(BaseModel):
    __tablename__ = 'course_ratings'

    course_id = Column(Integer, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(String(36), nullable=False)
    rating = Column(SmallInteger, nullable=False)

    course = relationship("Course", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_ratings_course_user"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_course_ratings_rating_range"),
        Index("ix_course_ratings_course_id_active", "course_id", postgresql_where="deleted_at IS NULL"),
        Index("ix_course_ratings_user_id_active", "user_id", postgresql_where="deleted_at IS NULL"),
    )

    def __repr__(self):
        return (
            f"<CourseRating(id={self.id}, course_id={self.course_id}, "
            f"user_id='{self.user_id}', rating={self.rating})>"
        )
