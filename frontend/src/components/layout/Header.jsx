import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { PanelLeft } from "lucide-react";
import { Root, Trigger, Content, Item } from "@radix-ui/react-dropdown-menu";
import { Button } from "@/components/ui/button";
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

  const goToSettings = () => {
    navigate(ROUTE_PATHS.SIGN_IN_SECURITY);
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
    <header className="fixed inset-x-0 top-0 z-[100] flex h-16 min-h-16 shrink-0 items-center justify-between border-b bg-background px-[30px] shadow-sm">
      <div className="flex items-center gap-2.5 text-2xl font-bold text-primary">
        {onToggleSidebar && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="rounded-lg"
            onClick={onToggleSidebar}
            aria-label={
              sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
            }
            aria-expanded={!sidebarCollapsed}
          >
            <PanelLeft size={20} />
          </Button>
        )}
        <img src={logo} alt="Purrf Logo" className="h-[35px] w-auto" />
        <span>Purrf</span>
      </div>
      <div className="flex items-center">
        <Root>
          <Trigger asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label="User menu"
              className="rounded-full bg-primary text-base font-bold text-primary-foreground hover:bg-primary/80 hover:text-primary-foreground"
            >
              <span>{char}</span>
            </Button>
          </Trigger>
          <Content
            align="end"
            side="bottom"
            className="rounded-lg border bg-popover p-1 text-popover-foreground shadow-sm outline-none"
          >
            <Item
              onClick={goToProfile}
              className="relative flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent"
              aria-label="View Profile"
            >
              View Profile
            </Item>
            <Item
              onClick={goToSettings}
              className="relative flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent"
              aria-label="Settings"
            >
              Settings
            </Item>
            <Item
              onClick={openContactUs}
              className="relative flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent"
              aria-label="Contact Us"
            >
              Contact Us
            </Item>
            <Item
              onClick={performGlobalLogout}
              className="relative flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent"
              aria-label="Logout"
            >
              Logout
            </Item>
          </Content>
        </Root>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogOverlay className="fixed inset-0 z-[999] bg-black/40" />
          <DialogContent
            className="fixed left-1/2 top-1/2 z-[1000] w-full max-w-[530px] -translate-x-1/2 -translate-y-1/2 rounded-lg bg-background p-[1.4rem] shadow-[0_10px_25px_rgba(0,0,0,0.1)]"
            role="dialog"
          >
            <div className="-mb-[0.1rem] -mt-4 flex items-center justify-between p-0 text-[10px]">
              <DialogTitle className="text-lg leading-tight font-semibold">
                Contact Administrators
              </DialogTitle>
              <DialogClose
                className="-mr-2 cursor-pointer border-none bg-transparent p-0 text-[22px] text-[#555555]"
                onClick={closeContactUs}
              >
                ×
              </DialogClose>
            </div>
            <div>
              <p className="-mt-2 mb-0 text-base text-[#555555b1]">
                If you need support, please contact our admins:
              </p>
              <div className="my-7"></div>
              <p className="font-normal text-[#555555]">Admin Email:</p>
              <p className="m-0 text-[#007bff]">
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
