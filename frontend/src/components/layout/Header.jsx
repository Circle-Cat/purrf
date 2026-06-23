import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./Header.css";
import { PanelLeft } from "lucide-react";
import { Root, Trigger, Content, Item } from "@radix-ui/react-dropdown-menu";
import logo from "@/assets/logo.png";
import {
  getCookie,
  extractCloudflareUserName,
  performGlobalLogout,
} from "@/utils/auth";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogClose,
  DialogOverlay,
} from "@radix-ui/react-dialog";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

/**
 * Top navigation bar. Optionally renders a button that toggles the sidebar's
 * collapsed state; the toggle is only shown when `onToggleSidebar` is provided.
 *
 * @param {Object} props
 * @param {() => void} [props.onToggleSidebar] - Toggles the sidebar collapsed state.
 * @param {boolean} [props.sidebarCollapsed] - Whether the sidebar is currently collapsed.
 * @returns {JSX.Element}
 */
const Header = ({ onToggleSidebar, sidebarCollapsed }) => {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [char, setChar] = useState("");
  const navigate = useNavigate();

  const goToProfile = () => {
    navigate(ROUTE_PATHS.PROFILE);
  };

  const openContactUs = () => {
    setIsDialogOpen(true);
  };

  const closeContactUs = () => {
    setIsDialogOpen(false);
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
        {onToggleSidebar && (
          <button
            type="button"
            className="sidebar-toggle"
            onClick={onToggleSidebar}
            aria-label={
              sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
            }
            aria-expanded={!sidebarCollapsed}
          >
            <PanelLeft size={20} />
          </button>
        )}
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
            <Item
              onClick={openContactUs}
              className="dropdown-item"
              aria-label="Contact Us"
            >
              Contact Us
            </Item>
            <Item
              onClick={performGlobalLogout}
              className="dropdown-item"
              aria-label="Logout"
            >
              Logout
            </Item>
          </Content>
        </Root>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogOverlay className="dialog-overlay" />
          <DialogContent className="dialog-content" role="dialog">
            <div className="dialog-header">
              <DialogTitle className="text-lg leading-tight font-semibold">
                Contact Administrators
              </DialogTitle>
              <DialogClose className="dialog-close" onClick={closeContactUs}>
                ×
              </DialogClose>
            </div>
            <div className="dialog-body">
              <p className="support-message">
                If you need support, please contact our admins:
              </p>
              <div className="spacer"></div>
              <p className="admin-email-text">Admin Email:</p>
              <p className="admin-email">
                outreach-programs-comms@circlecat.org
              </p>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </header>
  );
};

export default Header;
