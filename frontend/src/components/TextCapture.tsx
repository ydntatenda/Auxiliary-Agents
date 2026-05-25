type Props = {
  text: string;
  onChange: (value: string) => void;
};

export default function TextCapture({ text, onChange }: Props) {
  return (
    <textarea
      className="text-input"
      onChange={(event) => onChange(event.target.value)}
      placeholder="Walk through what happens, step by step. Don't worry about structure - Modus will ask follow-up questions to fill gaps."
      value={text}
    />
  );
}
