import { useCallback, useEffect, useState } from 'react';

import { loadWorkspace, saveWorkspace, type WorkspaceState } from '../lib/storage';

const workspaceEvent = 'pde:workspace-change';

export function useWorkspace(): [WorkspaceState, (next: WorkspaceState | ((current: WorkspaceState) => WorkspaceState)) => void] {
  const [workspace, setWorkspaceState] = useState<WorkspaceState>(() => loadWorkspace());

  useEffect(() => {
    const refresh = (): void => setWorkspaceState(loadWorkspace());
    window.addEventListener(workspaceEvent, refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener(workspaceEvent, refresh);
      window.removeEventListener('storage', refresh);
    };
  }, []);

  const update = useCallback((next: WorkspaceState | ((current: WorkspaceState) => WorkspaceState)): void => {
    setWorkspaceState((current) => {
      const resolved = typeof next === 'function' ? next(current) : next;
      saveWorkspace(resolved);
      window.dispatchEvent(new Event(workspaceEvent));
      return resolved;
    });
  }, []);

  return [workspace, update];
}
