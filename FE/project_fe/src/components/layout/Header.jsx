import React from "react";
import { User } from "lucide-react";

const Header = () => {
  return (
    <header
      className="
        sticky
        top-0 left-0 right-0
        z-20
        flex h-16 items-center
        bg-white border-b border-slate-200
        px-6
      "
    >
      <div className="flex items-center justify-between w-full h-full gap-2">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 bg-primary rounded-xl text-white flex items-center justify-center font-semibold">
            UI
          </div>
          <span className="font-semibold text-slate-800 text-lg">
            Automation Test System
          </span>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 border border-slate-200 text-slate-500 cursor-pointer hover:bg-slate-50 transition-colors">
            <User className="h-5 w-5" strokeWidth={3} />
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
