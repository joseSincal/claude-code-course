"use client";

import { useState } from "react";
import styles from "./StarRating.module.scss";

interface StarRatingProps {
  averageRating: number;
  totalRatings: number;
  courseId: string;
  userRating?: number;
  onRate?: (rating: number) => void;
}

interface StarProps {
  fill: number; // 0 to 1
  value: number;
  interactive: boolean;
  onMouseEnter?: () => void;
  onClick?: () => void;
}

function Star({ fill, value, interactive, onMouseEnter, onClick }: StarProps) {
  const label =
    fill >= 1
      ? `${value} estrella${value !== 1 ? "s" : ""}, llena`
      : fill > 0
      ? `${value} estrella${value !== 1 ? "s" : ""}, media`
      : `${value} estrella${value !== 1 ? "s" : ""}, vacía`;

  return (
    <span
      className={styles.starWrapper}
      aria-label={label}
      onMouseEnter={interactive ? onMouseEnter : undefined}
      onClick={interactive ? onClick : undefined}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onKeyDown={
        interactive && onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") onClick();
            }
          : undefined
      }
    >
      {/* Base: empty star */}
      <span className={styles.starEmpty}>&#9733;</span>
      {/* Overlay: filled star clipped to the fill percentage */}
      {fill > 0 && (
        <span
          className={styles.starFilled}
          style={{
            clipPath: `inset(0 ${Math.round((1 - fill) * 100)}% 0 0)`,
          }}
        >
          &#9733;
        </span>
      )}
    </span>
  );
}

export function StarRating({
  averageRating,
  totalRatings,
  courseId,
  userRating,
  onRate,
}: StarRatingProps) {
  const [hoverRating, setHoverRating] = useState<number | null>(null);

  const isInteractive = typeof onRate === "function";

  function getStarFill(starValue: number): number {
    const rating = isInteractive
      ? (hoverRating ?? userRating ?? 0)
      : averageRating;

    if (rating >= starValue) return 1;
    if (rating > starValue - 1) return rating - (starValue - 1);
    return 0;
  }

  return (
    <div
      className={styles.container}
      aria-label={`Calificación: ${averageRating.toFixed(1)} de 5 (${totalRatings} ${totalRatings === 1 ? "calificación" : "calificaciones"})`}
      onMouseLeave={isInteractive ? () => setHoverRating(null) : undefined}
      data-course-id={courseId}
    >
      <div className={styles.stars}>
        {[1, 2, 3, 4, 5].map((value) => (
          <Star
            key={value}
            value={value}
            fill={getStarFill(value)}
            interactive={isInteractive}
            onMouseEnter={
              isInteractive ? () => setHoverRating(value) : undefined
            }
            onClick={isInteractive && onRate ? () => onRate(value) : undefined}
          />
        ))}
      </div>
      <span className={styles.totalRatings}>({totalRatings})</span>
    </div>
  );
}
