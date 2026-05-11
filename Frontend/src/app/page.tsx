import styles from "./page.module.scss";
import { Course } from "@/types";
import { Course as CourseComponent } from "@/components/Course/Course";
import Link from "next/link";

interface ApiCourse {
  id: number;
  name: string;
  description: string;
  thumbnail: string;
  slug: string;
  average_rating: number;
  total_ratings: number;
}

async function getCourses(): Promise<Course[]> {
  const res = await fetch("http://localhost:8000/courses", { cache: "no-store" });
  if (!res.ok) {
    throw new Error("Failed to fetch courses");
  }
  const data: ApiCourse[] = await res.json();
  return data.map((item) => ({
    id: item.id,
    title: item.name,
    teacher: "",
    duration: 0,
    thumbnail: item.thumbnail,
    slug: item.slug,
    average_rating: item.average_rating,
    total_ratings: item.total_ratings,
  }));
}

export default async function Home() {
  const courses = await getCourses();

  return (
    <div className={styles.page}>
      {/* Banner superior */}
      <header className={styles.banner}>
        <span className={styles.bannerRed}>PLATZI</span>
        <span className={styles.bannerBlack}>FLIX</span>
        <span className={styles.bannerSub}>CURSOS</span>
      </header>
      {/* Nombres laterales */}
      <div className={styles.verticalLeft}>PLATZI</div>
      <div className={styles.verticalRight}>FLIX</div>
      {/* Grid de cursos */}
      <main className={styles.main}>
        <div className={styles.coursesGrid}>
          {courses.map((course) => (
            <Link href={`/course/${course.slug}`} key={course.id}>
              <CourseComponent
                id={course.id}
                title={course.title}
                teacher={course.teacher}
                duration={course.duration}
                thumbnail={course.thumbnail}
                slug={course.slug}
                average_rating={course.average_rating}
                total_ratings={course.total_ratings}
              />
            </Link>
          ))}
        </div>
      </main>
      {/* Fondo de cuadrícula */}
      <div className={styles.gridBg}></div>
    </div>
  );
}
