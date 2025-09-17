import { useState, useEffect } from "react";
import "./Header.css";
import logo from "@/assets/logo.png";
import { getCookie, extractCloudflareUserName } from "@/utils/auth";

const Header = () => {
  const [char, setChar] = useState("");
  useEffect(() => {
    const cloudflareJwtCookie = getCookie("CF_Authorization");
    if (cloudflareJwtCookie) {
      const extractedName = extractCloudflareUserName(cloudflareJwtCookie);
      if (extractedName && extractedName.length > 0) {
        setChar(extractedName.charAt(0).toUpperCase());
      }
    }
  }, []);

  return (
    <header className="header">
      <div className="header-left">
        <img src={logo} alt="Purrf Logo" className="logo" />
        <span className="logo-text">Purrf</span>
      </div>
      <div className="header-right">
        <span className="user-name">{char}</span>
      </div>
    </header>
  );
};

export default Header;
