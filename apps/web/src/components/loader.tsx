import "@/styles/loader.css";

/**
 * Calm "hide and seek" loader: the letters of a short word rise into view one after another.
 * The word and the note underneath are set per page (see `loading` in lib/copy.ts).
 * Screen readers get the label as plain text; the animated letters are decorative.
 */
export function Loader({
  label = "Loading",
  note,
  page = false,
}: {
  label?: string;
  note?: string;
  /** Centre the loader in the viewport, for full-page loading states. */
  page?: boolean;
}) {
  const letters = Array.from(label);
  return (
    <div className={`mr-loader${page ? " is-page" : ""}`} role="status" aria-live="polite">
      <span className="sr-only">{note ? `${label}. ${note}` : label}</span>
      <div className="mr-loader-word" aria-hidden="true">
        {letters.map((letter, index) =>
          letter === " " ? (
            <span key={index} className="mr-loader-gap" />
          ) : (
            <span
              key={index}
              className={`mr-loader-letter${index === 0 ? " is-accent" : ""}`}
              style={{ ["--i" as string]: index }}
            >
              <span>{letter}</span>
            </span>
          ),
        )}
      </div>
      {note ? (
        <p className="mr-loader-note" aria-hidden="true">
          {note}
        </p>
      ) : null}
    </div>
  );
}
