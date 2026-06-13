export interface StepDef {
  id: string;
  label: string;
  hint: string;
}

export function StepRail({
  steps,
  active,
  onSelect,
}: {
  steps: StepDef[];
  active: string;
  onSelect: (id: string) => void;
}) {
  const activeIndex = steps.findIndex((s) => s.id === active);
  return (
    <aside className="step-rail glass">
      <ol>
        {steps.map((step, i) => {
          const state =
            i < activeIndex ? "done" : i === activeIndex ? "active" : "todo";
          return (
            <li key={step.id}>
              <button
                className={`step-item is-${state}`}
                onClick={() => onSelect(step.id)}
              >
                <span className="step-index">{state === "done" ? "✓" : i + 1}</span>
                <span className="step-body">
                  <strong>{step.label}</strong>
                  <em>{step.hint}</em>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
