import styles from "./Course.module.scss";
import { Course as CourseType } from "@/types";
import { StarRating } from "@/components/StarRating/StarRating";

export const Course = ({
  id,
  title,
  teacher,
  duration,
  thumbnail,
  slug,
  average_rating,
  total_ratings,
}: CourseType) => {
  return (
    <article className={styles.courseCard}>
      <div className={styles.thumbnailContainer}>
        <img src={thumbnail} alt={title} className={styles.thumbnail} />
      </div>
      <div className={styles.courseInfo}>
        <h2 className={styles.courseTitle}>{title}</h2>
        <p className={styles.teacher}>Profesor: {teacher}</p>
        <p className={styles.duration}>Duración: {duration} minutos</p>
        <StarRating
          averageRating={average_rating ?? 0}
          totalRatings={total_ratings ?? 0}
          courseId={slug}
        />
      </div>
    </article>
  );
};
