const Footer = () => {
  return (
    <footer className="h-12 bg-white border-t border-slate-200 px-6 flex items-center justify-between text-xs text-slate-500">
      <span>© {new Date().getFullYear()} Final Project</span>
      <span>React + TailwindCSS</span>
    </footer>
  );
};

export default Footer;
