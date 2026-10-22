import type { ReactNode } from "react";
import s from "./Panel.module.css";

export function Panel({ title, right, children, className }: { title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`${s.panel} ${className ?? ""}`}>
      <h2 className={s.title}><span>{title}</span>{right}</h2>
      <div className={s.body}>{children}</div>
    </section>
  );
}
