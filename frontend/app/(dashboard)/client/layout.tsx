import type { ReactNode } from 'react';
import { ClientShell } from './_components/client-shell';

export default function ClientLayout({ children }: { children: ReactNode }) {
  return <ClientShell>{children}</ClientShell>;
}
