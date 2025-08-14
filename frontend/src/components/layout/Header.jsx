import "./Header.css";
import logo from "../../assets/logo.png";

const Header = () => {
  return (
    <header className="header">
      <div className="header-left">
        <img src={logo} alt="Purrf Logo" className="logo" />
        <span className="logo-text">Purrf</span>
      </div>
      <div className="header-right">
        <span className="user-name">Y</span>
      </div>
    </header>
  );
};

export default Header;
