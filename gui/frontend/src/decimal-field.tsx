import { useEffect, useRef, useState } from 'react';
import { decimalValue } from './decimal-input';
export default function DecimalField({
  value,
  scale = 1,
  onChange,
  onValidity,
  ...props
}: {
  value: number;
  scale?: number;
  onChange: (value: number) => void;
  onValidity?: (valid: boolean) => void;
  'aria-label': string;
  disabled?: boolean;
}) {
  const [text, setText] = useState(Number.isFinite(value) ? String(value / scale) : '');
  const previousValue = useRef(value);
  useEffect(() => {
    const parsed = decimalValue(text);
    if (
      value !== previousValue.current &&
      Number.isFinite(value) &&
      (parsed === null || Math.abs(parsed * scale - value) > 1e-8)
    ) {
      setText(String(value / scale));
      onValidity?.(true);
    }
    previousValue.current = value;
  }, [value, scale]);
  useEffect(() => () => onValidity?.(true), []);
  return (
    <input
      {...props}
      type="text"
      inputMode="decimal"
      value={text}
      aria-invalid={decimalValue(text) === null}
      onChange={(e) => {
        const raw = e.target.value;
        setText(raw);
        const n = decimalValue(raw);
        onValidity?.(n !== null);
        if (n !== null) onChange(n * scale);
      }}
    />
  );
}
