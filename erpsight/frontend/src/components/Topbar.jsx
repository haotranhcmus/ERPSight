export default function Topbar({ title, children }) {
  return (
    <header className="topbar">
      <h1>{title}</h1>
      {children}
    </header>
  );
}
