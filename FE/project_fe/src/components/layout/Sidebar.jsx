// src/components/layout/Sidebar.jsx
import { NavLink } from "react-router-dom";
import ROUTES from "../../routes/routes";

export default function Sidebar() {
  const menus = [
    { label: "Dashboard", path: ROUTES.DASHBOARD },
    { label: "Projects", path: ROUTES.PROJECTS },
    { label: "Knowledge Base", path: ROUTES.KNOWLEDGE_BASE },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200 p-4">
      <nav className="flex flex-col gap-1">
        {menus.map((menu) => (
          <NavLink
            key={menu.path}
            to={menu.path}
            // với "/" thì cần end để không active khi đang ở /projects, /knowledge-base
            end={menu.path === ROUTES.DASHBOARD}
            className={({ isActive }) =>
              `px-4 py-2 rounded-lg text-sm font-medium transition ${
                isActive
                  ? "bg-primary text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`
            }
          >
            {menu.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
