import './globals.css'

export const metadata = {
  title: 'Frontend App',
  description: 'Next.js Frontend Application',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
