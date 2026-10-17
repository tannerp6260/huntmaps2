import { useEffect, useRef, useState } from 'react';
import { decimalValue } from './decimal-input';
export default function DecimalField({
  value,
  scale = 1,
  onChange,
  onValidity,
  min = 0,
  max = Infinity,
  integer = false,
  ...props
}: {
  value: number;
  scale?: number;
  onChange: (value: number) => void;
  onValidity?: (valid: boolean) => void;
  min?: number;
  max?: number;
  integer?: boolean;
  'aria-label': string;
  disabled?: boolean;
}) {
  const [text, setText] = useState(Number.isFinite(value) ? String(value / scale) : '');
  const previousValue = useRef(value);
  const callback = useRef(onValidity);
  callback.current = onValidity;
  const parsed = decimalValue(text);
  const valid =
    parsed !== null && parsed >= min && parsed <= max && (!integer || Number.isInteger(parsed));
  useEffect(() => {
    callback.current?.(valid);
  }, [valid]);
  useEffect(() => {
    if (
      !Object.is(value, previousValue.current) &&
      Number.isFinite(value) &&
      (parsed === null || Math.abs(parsed * scale - value) > 1e-8)
    )
      setText(String(value / scale));
    previousValue.current = value;
  }, [value, scale]);
  useEffect(() => () => callback.current?.(true), []);
  return (
    <input
      {...props}
      type="text"
      inputMode={integer ? 'numeric' : 'decimal'}
      autoComplete="off"
      name={'terrain-' + props['aria-label'].toLowerCase().replace(/[^a-z0-9]+/g, '-')}
      value={text}
      aria-invalid={!valid}
      onBlur={() => {
        if (valid) setText(String(parsed));
      }}
      onChange={(e) => {
        const raw = e.target.value;
        setText(raw);
        const n = decimalValue(raw);
        const ok = n !== null && n >= min && n <= max && (!integer || Number.isInteger(n));
        callback.current?.(ok);
        onChange(ok ? n! * scale : NaN);
      }}
    />
  );
}
