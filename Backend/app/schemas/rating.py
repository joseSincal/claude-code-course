from pydantic import BaseModel, Field


class RatingCreate(BaseModel):
    user_id: str = Field(min_length=36, max_length=36)
    rating: int = Field(ge=1, le=5)


class RatingResponse(BaseModel):
    course_id: int
    user_id: str
    rating: int
    average_rating: float
    total_ratings: int


class UserRatingResponse(BaseModel):
    course_id: int
    user_id: str
    rating: int
