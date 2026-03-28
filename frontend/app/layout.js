import './globals.css'

export const metadata = {
  title: 'inLaw',
  description: 'ИИ-анализ юридических документов',
  icons: {
    icon: '/inlawlogo.svg',
  },
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
