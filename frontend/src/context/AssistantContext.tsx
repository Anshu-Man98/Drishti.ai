import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

interface AssistantContextType {
  isClaimPickerOpen: boolean;
  openAssistant: (targetClaimId?: string) => void;
  closeClaimPicker: () => void;
  registerClaimDetailChatOpener: (opener: () => void) => () => void;
  isChatOpenOnClaim: boolean;
  setIsChatOpenOnClaim: (open: boolean) => void;
}

const AssistantContext = createContext<AssistantContextType | undefined>(undefined);

export const AssistantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isClaimPickerOpen, setIsClaimPickerOpen] = useState(false);
  const [isChatOpenOnClaim, setIsChatOpenOnClaim] = useState(false);
  const claimDetailOpenerRef = useRef<(() => void) | null>(null);
  const location = useLocation();
  const navigate = useNavigate();

  const registerClaimDetailChatOpener = useCallback((opener: () => void) => {
    claimDetailOpenerRef.current = opener;
    return () => {
      claimDetailOpenerRef.current = null;
    };
  }, []);

  const openAssistant = useCallback((targetClaimId?: string) => {
    if (targetClaimId) {
      if (location.pathname === `/claims/${targetClaimId}`) {
        claimDetailOpenerRef.current?.();
      } else {
        navigate(`/claims/${targetClaimId}?chat=open`);
      }
      setIsClaimPickerOpen(false);
      return;
    }

    // Check if we are currently on a claim detail page
    const claimMatch = location.pathname.match(/^\/claims\/([^/]+)$/);
    if (claimMatch && claimMatch[1] && claimMatch[1] !== 'new') {
      if (claimDetailOpenerRef.current) {
        claimDetailOpenerRef.current();
      } else {
        setIsChatOpenOnClaim(true);
      }
      setIsClaimPickerOpen(false);
    } else {
      // General route: Open claim picker dialog
      setIsClaimPickerOpen(true);
    }
  }, [location.pathname, navigate]);

  const closeClaimPicker = useCallback(() => {
    setIsClaimPickerOpen(false);
  }, []);

  // Global Keyboard Shortcut: '/' or 'Ctrl+K' / 'Cmd+K' when no input is focused
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is typing in an input, textarea, or contentEditable
      const target = e.target as HTMLElement | null;
      const tagName = target?.tagName?.toLowerCase();
      const isInput = tagName === 'input' || tagName === 'textarea' || tagName === 'select' || target?.isContentEditable;

      const isSlash = e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey;
      const isCmdK = (e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k';

      if ((isSlash && !isInput) || isCmdK) {
        e.preventDefault();
        openAssistant();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [openAssistant]);

  return (
    <AssistantContext.Provider
      value={{
        isClaimPickerOpen,
        openAssistant,
        closeClaimPicker,
        registerClaimDetailChatOpener,
        isChatOpenOnClaim,
        setIsChatOpenOnClaim,
      }}
    >
      {children}
    </AssistantContext.Provider>
  );
};

const defaultAssistantContext: AssistantContextType = {
  isClaimPickerOpen: false,
  openAssistant: () => {},
  closeClaimPicker: () => {},
  registerClaimDetailChatOpener: () => () => {},
  isChatOpenOnClaim: false,
  setIsChatOpenOnClaim: () => {},
};

export const useAssistant = (): AssistantContextType => {
  const context = useContext(AssistantContext);
  return context || defaultAssistantContext;
};
