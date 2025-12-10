import React from "react";

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
            F
          </div>
          <span className="font-semibold text-slate-800 text-lg">
            Final Project
          </span>
        </div>

        <div className="flex items-center space-x-4">
          <div className="h-9 w-9 rounded-full bg-slate-300" />
        </div>
      </div>
    </header>
  );
};

export default Header;
