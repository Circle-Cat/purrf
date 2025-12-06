import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./Header.css";
import { Root, Trigger, Content, Item } from "@radix-ui/react-dropdown-menu";
import logo from "@/assets/logo.png";
import { getCookie, extractCloudflareUserName } from "@/utils/auth";

const Header = () => {
  const [char, setChar] = useState("");
  const navigate = useNavigate();

  const goToProfile = () => {
    navigate("/profile");
  };

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
        <Root>
          <Trigger asChild>
            <button className="user-name">
              <span>{char}</span>
            </button>
          </Trigger>
          <Content align="end" side="bottom" className="dropdown-content">
            <Item
              onClick={goToProfile}
              className="dropdown-item"
              aria-label="View Profile"
            >
              View Profile
            </Item>
          </Content>
        </Root>
      </div>
    </header>
  );
};

export default Header;
