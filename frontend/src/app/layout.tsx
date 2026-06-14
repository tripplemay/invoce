import React, { ReactNode } from 'react';
import AppWrappers from './AppWrappers';
// import '@asseinfo/react-kanban/dist/styles.css';
// import '/public/styles/Plugins.css';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="dark" id={'root'}>
        <AppWrappers>{children}</AppWrappers>
      </body>
    </html>
  );
}
